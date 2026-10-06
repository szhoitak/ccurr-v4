# 第 8 章：`ccurr-strategy` 引擎架構

> 本章定義策略引擎的三層架構實作：Layer 1（引擎）、Layer 2（插件）、Layer 3（模式）。

---

## 8.0 為什麼要三層架構

### 8.0.1 問題

如果把 Step 1~9 全部寫死在一個容器裡：

| 問題                 | 說明                   |
| -------------------- | ---------------------- |
| **無法擴展**   | 新增策略要改主程式     |
| **無法熱重載** | 改參數要重啟容器       |
| **無法比較**   | 多策略無法並行運行     |
| **無法回測**   | 掃描邏輯與歷史資料耦合 |
| **除錯困難**   | 所有邏輯混在一起       |

### 8.0.2 三層架構解決什麼

```text
Layer 1：策略引擎（Engine）
  ├── 定時觸發
  ├── 載入策略插件
  ├── 執行掃描
  ├── 管理生命週期
  └── 錯誤處理
        ↓
Layer 2：策略插件（Plugins）
  ├── 每個策略獨立檔案
  ├── 實作 BaseStrategy
  ├── 定義 Step 1~9
  └── 可熱重載
        ↓
Layer 3：決策模式（Modes）
  ├── MANUAL / SEMI / AUTO
  ├── 每個策略可獨立設定
  └── 決定候選如何處理
```

## 8.1 整體架構圖

```text
┌─────────────────────────────────────────────────────────────┐
│                   ccurr-strategy                            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Layer 1: StrategyEngine                   │ │
│  │                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │ PluginLoader │  │  Scheduler   │  │ TaskRunner │  │ │
│  │  │              │  │              │  │ (60s 超時) │  │ │
│  │  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │ │
│  │         │                  │                 │         │ │
│  │         ▼                  ▼                 ▼         │ │
│  │  ┌──────────────────────────────────────────────┐    │ │
│  │  │           StrategyContext Builder             │    │ │
│  │  └──────────────────────────────────────────────┘    │ │
│  │                                                        │ │
│  │  ┌──────────────────────────────────────────────┐    │ │
│  │  │  ConfigWatcher (訂閱 config:changed)          │    │ │
│  │  │  → 事件驅動熱重載（毫秒級）                    │    │ │
│  │  └──────────────────────────────────────────────┘    │ │
│  │                                                        │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                           ▼ 序列執行                          │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Layer 2: Strategy Plugins                 │ │
│  │  ┌─────────────────────┐  ┌─────────────────────┐    │ │
│  │  │ volume_breakout_    │  │  (未來策略)          │    │ │
│  │  │ pullback_v1         │  │                     │    │ │
│  │  │  Step1~9 類別       │  │                     │    │ │
│  │  └─────────────────────┘  └─────────────────────┘    │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Layer 3: Decision Modes                   │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │ │
│  │  │ MANUAL   │  │  SEMI    │  │  AUTO    │            │ │
│  │  └──────────┘  └──────────┘  └──────────┘            │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           ▼                                  │
│               publish("signal:all")                          │
└───────────────────────────┼──────────────────────────────────┘
                            ▼
                    ccurr-executor
```

## 8.2 Layer 1：策略引擎

### 8.2.1 職責

| 職責                   | 說明                                     |
| ---------------------- | ---------------------------------------- |
| **定時觸發**     | 依排程執行掃描                           |
| **載入插件**     | 動態載入`plugins/`目錄的策略           |
| **建立 Context** | 提供策略存取 ClickHouse / Redis / Config |
| **執行掃描**     | 呼叫策略的`scan()`                     |
| **錯誤隔離**     | 單一策略失敗不影響其他                   |
| **熱重載**       | 訂閱`config:changed`                   |
| **記錄**         | 追蹤、審計、統計                         |

### 8.2.2 目錄結構

```text
app/engine/
├── __init__.py
├── strategy_engine.py      # 主引擎
├── plugin_loader.py        # 插件載入器
├── plugin_registry.py      # 插件註冊表
├── context_builder.py      # StrategyContext 建構
├── scheduler.py            # 排程
├── task_runner.py          # 任務執行
├── config_watcher.py       # 配置監聽
└── health.py               # 健康檢查
```

### 8.2.3 `StrategyEngine` 類別

```python
class StrategyEngine:
    """策略引擎主類別"""

    def __init__(
        self,
        settings: StrategySettings,
        clickhouse_reader,
        redis_client,
        config_client,
        dbwriter_client,
        trace_recorder,
        event_publisher,
        audit_logger,
        degradation_reader,
    ):
        self._settings = settings
        self._clickhouse = clickhouse_reader
        self._redis = redis_client
        self._config = config_client
        self._dbwriter = dbwriter_client
        self._trace = trace_recorder
        self._publisher = event_publisher
        self._audit = audit_logger
        self._degradation = degradation_reader

        # 核心元件
        self._loader = PluginLoader(settings.plugins_dir)
        self._registry = PluginRegistry()
        self._context_builder = ContextBuilder(
            clickhouse_reader, redis_client, config_client,
        )
        self._scheduler = Scheduler()

        # ModeHandler（先建立，注入 engine；context / config 稍後注入）
        self._mode_handler = ModeHandler(
            redis_client,
            event_publisher,
            engine=self,
            config=config_client,
        )

        # TaskRunner（注入 mode_handler，避免內部自行 new）
        self._task_runner = TaskRunner(
            redis_client,
            event_publisher,
            trace_recorder,
            audit_logger,
            dbwriter_client,
            settings,
            mode_handler=self._mode_handler,
        )

        self._config_watcher = ConfigWatcher(
            redis_client, self, settings,
        )

        # 狀態
        self._stop_event = asyncio.Event()
        self._strategies: dict[str, BaseStrategy] = {}

    async def start(self) -> None:
        """啟動引擎"""
        log.info("engine_starting")

        # 1. 載入所有插件
        await self._load_plugins()

        # 2. 啟動配置監聽（事件驅動）
        await self._config_watcher.start()

        # 3. 啟動排程
        await self._scheduler.start(self._run_scan_cycle)

        # 4. 啟動超時輪詢（Step 7 的 ZSET）
        await self._task_runner.start_review_timeout_loop()

        log.info("engine_started",
                 strategies=list(self._strategies.keys()))

    async def stop(self) -> None:
        """停止引擎"""
        log.info("engine_stopping")
        self._stop_event.set()

        await self._scheduler.stop()
        await self._config_watcher.stop()
        await self._task_runner.stop()

        for strategy in self._strategies.values():
            await strategy.on_stop()

        log.info("engine_stopped")

    async def _load_plugins(self) -> None:
        """載入所有策略插件"""
        plugins = self._loader.load_all()

        for strategy_id, strategy_cls in plugins.items():
            try:
                # 讀取策略配置
                config = await self._config.load_strategy_config(strategy_id)

                if not config.get("enabled", False):
                    log.info("strategy_disabled", strategy_id=strategy_id)
                    continue

                # 建立實例
                strategy = strategy_cls(config, self._context_builder)

                # 驗證配置
                if not strategy.validate_config():
                    log.error("invalid_strategy_config",
                             strategy_id=strategy_id)
                    continue

                # 啟動策略
                context = await self._context_builder.build(strategy_id)
                await strategy.on_start(context)

                self._strategies[strategy_id] = strategy
                self._registry.register(strategy_id, strategy)

                # 注入 context 到 ModeHandler（供 _handle_manual_entry 使用）
                # 第一版只有一個策略，直接覆寫；
                # 未來多策略時改為 dict[strategy_id, context]
                self._mode_handler.set_context(context)

                log.info("strategy_loaded",
                         strategy_id=strategy_id,
                         version=strategy.version)
            except Exception as e:
                log.error("strategy_load_failed",
                         strategy_id=strategy_id,
                         error=str(e))

    async def _run_scan_cycle(self) -> None:
        """執行一次完整掃描週期"""
        run_start = self._context.now_ms()

        # 檢查降級狀態
        can_proceed, reason = await self._check_degradation()
        if not can_proceed:
            log.warning("scan_skipped_degraded", reason=reason)
            return

        # 序列執行每個策略
        for strategy_id, strategy in self._strategies.items():
            try:
                await self._task_runner.run_strategy(
                    strategy_id, strategy,
                )
            except Exception as e:
                log.error("strategy_run_failed",
                         strategy_id=strategy_id,
                         error=str(e))

        log.info("scan_cycle_complete",
                 duration_ms=self._context.now_ms() - run_start)

    async def _check_degradation(self) -> tuple[bool, str]:
        """檢查降級狀態"""
        matrix = await self._degradation.get_matrix()

        accountsync = matrix.services.get("ccurr-accountsync")
        if accountsync and accountsync.level == "down":
            return False, "accountsync_down"

        return True, ""

    async def reload_strategy(self, strategy_id: str) -> None:
        """熱重載單一策略"""
        log.info("strategy_reloading", strategy_id=strategy_id)

        # 1. 停止舊實例
        old_strategy = self._strategies.get(strategy_id)
        if old_strategy:
            await old_strategy.on_stop()

        # 2. 重新載入類別
        strategy_cls = self._loader.reload_strategy(strategy_id)
        if not strategy_cls:
            log.error("strategy_class_not_found",
                     strategy_id=strategy_id)
            return

        # 3. 讀取新配置
        new_config = await self._config.load_strategy_config(strategy_id)

        # 4. 建立新實例
        new_strategy = strategy_cls(new_config, self._context_builder)
        context = await self._context_builder.build(strategy_id)
        await new_strategy.on_start(context)

        # 5. 替換
        self._strategies[strategy_id] = new_strategy
        self._registry.register(strategy_id, new_strategy)

        # 同步更新 ModeHandler 的 context
        self._mode_handler.set_context(context)

        log.info("strategy_reloaded", strategy_id=strategy_id)

    async def reload_all_strategies(self) -> None:
        """熱重載所有策略"""
        for strategy_id in list(self._strategies.keys()):
            await self.reload_strategy(strategy_id)

    async def execute_step8_pricing(
        self,
        candidate: Candidate,
        custom_tp: Decimal | None = None,
    ) -> None:
        """執行 Step 8（由 ModeHandler 或 UDS 呼叫）"""
        strategy = self._strategies.get(candidate.strategy_id)
        if not strategy:
            log.error("strategy_not_found",
                     strategy_id=candidate.strategy_id)
            return

        signal = await strategy.on_candidate_confirmed(
            candidate, custom_tp,
        )

        if signal:
            await self._publisher.publish(
                channel="signal:all",
                event_type="signal.generated",
                payload=signal.model_dump(),
                trace_id=signal.traceId,
            )
```

### 8.2.4 `PluginLoader` 類別

```python
class PluginLoader:
    """動態載入策略插件"""

    def __init__(self, plugins_dir: str):
        self._dir = plugins_dir
        self._loaded: dict[str, type[BaseStrategy]] = {}

    def load_all(self) -> dict[str, type[BaseStrategy]]:
        """掃描 plugins 目錄，載入所有策略"""
        self._loaded = {}

        if not os.path.exists(self._dir):
            log.warning("plugins_dir_not_exists", dir=self._dir)
            return {}

        for filename in os.listdir(self._dir):
            if not self._is_strategy_file(filename):
                continue
            self._load_file(filename)

        return self._loaded

    def _is_strategy_file(self, filename: str) -> bool:
        if not filename.endswith(".py"):
            return False
        if filename.startswith("_"):
            return False
        if filename in (
            "base_strategy.py", "base_step.py",
            "models.py", "context.py",
        ):
            return False
        return True

    def _load_file(self, filename: str) -> None:
        """載入單一檔案"""
        module_name = filename[:-3]
        file_path = os.path.join(self._dir, filename)

        try:
            spec = importlib.util.spec_from_file_location(
                module_name, file_path,
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj)
                    and issubclass(obj, BaseStrategy)
                    and obj is not BaseStrategy):

                    strategy_id = obj.strategy_id
                    if not strategy_id:
                        log.warning("strategy_missing_id",
                                   class_name=name)
                        continue

                    self._loaded[strategy_id] = obj
                    log.info("plugin_loaded",
                             strategy_id=strategy_id,
                             class_name=name)
        except Exception as e:
            log.error("plugin_load_failed",
                     filename=filename,
                     error=str(e))

    def reload_strategy(
        self,
        strategy_id: str,
    ) -> type[BaseStrategy] | None:
        """熱重載單一策略"""
        self.load_all()
        return self._loaded.get(strategy_id)
```

### 8.2.5 `PluginRegistry` 類別

```python
class PluginRegistry:
    """插件註冊表"""

    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, strategy_id: str, strategy: BaseStrategy) -> None:
        self._strategies[strategy_id] = strategy

    def unregister(self, strategy_id: str) -> None:
        self._strategies.pop(strategy_id, None)

    def get(self, strategy_id: str) -> BaseStrategy | None:
        return self._strategies.get(strategy_id)

    def list_all(self) -> dict[str, BaseStrategy]:
        return dict(self._strategies)

    def list_ids(self) -> list[str]:
        return list(self._strategies.keys())
```

### 8.2.6 `ContextBuilder` 類別

```python
class ContextBuilder:
    """建立 StrategyContext"""

    def __init__(
        self,
        clickhouse_reader,
        redis_client,
        config_client,
        clock: "Clock",
    ):
        self._clickhouse = clickhouse_reader
        self._redis = redis_client
        self._config = config_client
        self._clock = clock

    async def build(self, strategy_id: str) -> StrategyContext:
        """為策略建立符合 Chapter 9 canonical contract 的執行上下文"""
        return StrategyContext(
            clickhouse_reader=self._clickhouse,
            redis_client=self._redis,
            config_client=self._config,
            strategy_id=strategy_id,
            clock=self._clock,
        )
```

> 實作需由 `shared.locks.DistributedLock` 提供 Lua/token-safe lease，並由 constructor 注入 `dbwriter_client`；若 MariaDB terminal update 失敗，不得清理 Redis pending state 或執行後續 Signal。

```python
class Scheduler:
    """定時排程"""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(
        self,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        """啟動排程"""
        self._callback = callback
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        """主迴圈"""
        while not self._stop_event.is_set():
            try:
                await self._callback()
            except Exception as e:
                log.error("scheduled_run_failed", error=str(e))

            # 等待下一個週期
            try:
                interval = await self._get_scan_interval()
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval,
                )
            except asyncio.TimeoutError:
                pass

    async def _get_scan_interval(self) -> int:
        """讀取掃描間隔"""
        return 900  # 預設 15 分鐘

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task
```

### 8.2.8 `TaskRunner` 類別

```python
class TaskRunner:
    """任務執行器（含 60 秒超時）"""

    def __init__(
        self,
        redis_client,
        publisher,
        trace_recorder,
        audit_logger,
        dbwriter_client,
        settings,
        mode_handler: "ModeHandler | None" = None,
    ):
        self._redis = redis_client
        self._publisher = publisher
        self._trace = trace_recorder
        self._audit = audit_logger
        self._dbwriter = dbwriter_client
        self._settings = settings
        self._mode_handler = mode_handler
        self._stop_event = asyncio.Event()
        self._review_task: asyncio.Task | None = None

    def set_mode_handler(self, mode_handler: "ModeHandler") -> None:
        """由 StrategyEngine 在初始化後注入"""
        self._mode_handler = mode_handler

    async def run_strategy(
        self,
        strategy_id: str,
        strategy: BaseStrategy,
    ) -> None:
        """執行單一策略（含 60 秒超時）"""
        run_id = str(uuid.uuid4())
        start_ts = self._context.now_ms()

        await self._start_run_log(run_id, strategy_id)

        try:
            # 【核心】60 秒超時
            candidates = await asyncio.wait_for(
                strategy.scan(),
                timeout=60.0,
            )

            for candidate in candidates:
                await self._process_candidate(strategy_id, candidate)

            await self._finish_run_log(
                run_id, "success", len(candidates),
                self._context.now_ms() - start_ts,
            )
        except asyncio.TimeoutError:
            log.error("strategy_scan_timeout",
                     strategy_id=strategy_id,
                     timeout_sec=60)

            await self._finish_run_log(
                run_id, "timeout", 0, self._context.now_ms() - start_ts,
            )

            await self._publisher.publish_alert(
                level="critical",
                category="strategy_scan_timeout",
                message=f"策略 {strategy_id} 掃描超時（> 60 秒）",
                metadata={"strategy_id": strategy_id},
            )
        except Exception as e:
            await self._finish_run_log(
                run_id, "failed", 0, self._context.now_ms() - start_ts,
                error=str(e),
            )
            raise

    async def _process_candidate(
        self,
        strategy_id: str,
        candidate: Candidate,
    ) -> None:
        """依模式處理候選"""
        if self._mode_handler is None:
            log.error("mode_handler_not_set",
                     strategy_id=strategy_id,
                     trace_id=candidate.trace_id)
            return

        # 讀取策略模式
        mode = await self._get_strategy_mode(strategy_id)

        # 用注入的 ModeHandler（內含 engine / context）
        await self._mode_handler.process(candidate, mode)

    async def _get_strategy_mode(self, strategy_id: str) -> str:
        """讀取策略模式"""
        # 從 MariaDB strategies 表讀取
        # 或從 Redis 快取
        return "SEMI"

    # ============================================================
    # Step 7 超時輪詢
    # ============================================================

    async def start_review_timeout_loop(self) -> None:
        """啟動 Step 7 超時輪詢"""
        self._review_task = asyncio.create_task(self._review_loop())

    async def _review_loop(self) -> None:
        """每 30 秒檢查超時待審核"""
        while not self._stop_event.is_set():
            try:
                await self._check_review_timeouts()
            except Exception as e:
                log.error("review_timeout_check_failed",
                         error=str(e))

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=30,
                )
            except asyncio.TimeoutError:
                pass

    async def _check_review_timeouts(self) -> None:
        """檢查超時待審核"""
        now = self._context.now_ms()  # ⚠️ 必須是 13 位毫秒整數

        expired = await self._redis.zrangebyscore(
            "strategy:pending_reviews", 0, now,
        )

        for trace_id in expired:
            lock_key = f"lock:candidate:review:{trace_id}"
            async with DistributedLock(self._redis, lock_key, ttl_sec=10):
                # Confirm 與 Timeout 共用鎖；取得後再次檢查 active Set
                is_active = await self._redis.sismember(
                    "strategy:pending_review:active", trace_id,
                )
                if not is_active:
                    log.info("review_timeout_skipped_inactive", trace_id=trace_id)
                    continue

                candidate_json = await self._redis.hget(
                    "strategy:candidate_data", trace_id,
                )
                if not candidate_json:
                    continue

                candidate = Candidate.model_validate_json(candidate_json)
                candidate.status = "AUTO_APPROVED"
                candidate.review_action = "TIMEOUT_AUTO"
                candidate.review_responded_at_ms = now

                # 先更新 MariaDB terminal status，再以 pipeline 清理熱狀態
                await self._dbwriter.update_candidate_status(
                    trace_id, "TIMEOUT_AUTO", candidate.review_action, now,
                )
                if self._mode_handler is not None:
                    await self._mode_handler._handle_auto(candidate)
                await self._cleanup_pending_review(trace_id)

    async def _cleanup_pending_review(self, trace_id: str) -> None:
        """清理待審核 Redis 結構"""
        pipeline = self._redis.pipeline()
        pipeline.zrem("strategy:pending_reviews", trace_id)
        pipeline.hdel("strategy:candidate_data", trace_id)
        pipeline.srem("strategy:pending_review:active", trace_id)
        await pipeline.execute()

    async def _start_run_log(
        self,
        run_id: str,
        strategy_id: str,
    ) -> None:
        """寫入 run log 開始"""
        await self._redis.hset(
            f"strategy:run:{run_id}",
            mapping={
                "runId": run_id,
                "strategyId": strategy_id,
                "startedAt": self._context.now_ms(),
                "status": "running",
            },
        )
        await self._redis.sadd("strategy:runs:pending", run_id)

    async def _finish_run_log(
        self,
        run_id: str,
        status: str,
        candidates: int,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        """寫入 run log 結束"""
        await self._redis.hset(
            f"strategy:run:{run_id}",
            mapping={
                "finishedAt": self._context.now_ms(),
                "status": status,
                "candidates": candidates,
                "durationMs": duration_ms,
                "error": error or "",
            },
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._review_task:
            await self._review_task
```

### 8.2.9 `ConfigWatcher` 類別（事件驅動）

```python
class ConfigWatcher:
    """監聽配置變化（事件驅動）"""

    def __init__(
        self,
        redis_client,
        engine: StrategyEngine,
        settings,
    ):
        self._redis = redis_client
        self._engine = engine
        self._settings = settings
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        """訂閱 config:changed 頻道"""
        while not self._stop_event.is_set():
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe("config:changed")

                async for message in pubsub.listen():
                    if self._stop_event.is_set():
                        break
                    if message["type"] != "message":
                        continue

                    try:
                        payload = json.loads(message["data"])
                        await self._handle_config_change(payload)
                    except Exception as e:
                        log.error("config_change_failed", error=str(e))
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("config_watcher_error", error=str(e))
                await asyncio.sleep(5)
            finally:
                await pubsub.unsubscribe()
                await pubsub.close()

    async def _handle_config_change(self, payload: dict) -> None:
        """處理配置變更"""
        scope = payload.get("scope")
        strategy_id = payload.get("strategy_id")

        if scope != "strategy":
            return

        if strategy_id:
            await self._engine.reload_strategy(strategy_id)
        else:
            await self._engine.reload_all_strategies()
```

## 8.3 Layer 2：策略插件

### 8.3.1 檔案結構

```text
app/plugins/
├── __init__.py
├── base_strategy.py              # BaseStrategy 抽象類
├── base_step.py                  # BaseStep 抽象類（可選）
├── models.py                     # Candidate, Signal, 中間模型
├── context.py                    # StrategyContext
├── volume_breakout_pullback_v1.py  # 具體策略
└── steps/
    ├── __init__.py
    ├── step1_scanner.py
    ├── step2_volume_scanner.py
    ├── step3_volume_checker.py
    ├── step4_phase1_detector.py
    ├── step5_phase2_detector.py
    ├── step6_support_zone_checker.py
    ├── step7_candidate_builder.py
    └── step8_pricing.py
```

### 8.3.2 `BaseStrategy`、`StrategyContext` 與 Step 介面（非規範摘要）

> 本節僅說明引擎如何使用插件介面，不是第二份契約。唯一規範定義在 [Chapter 9](BLUEPRINT-PART05-Chapter09-10-StrategyPluginInterface.md) §9.1–§9.4；本節若與 Chapter 9 不一致，以 Chapter 9 為準。

```python
class BaseStrategy(ABC):
    """所有策略的抽象基底類別"""

    # ============================================================
    # 類別屬性（子類必須覆寫）
    # ============================================================

    strategy_id: str = ""
    strategy_name: str = ""
    version: str = "1.0"
    description: str = ""

    # ============================================================
    # 建構子
    # ============================================================

    def __init__(
        self,
        config: dict[str, Any],
        context_builder: "ContextBuilder",
    ):
        self._config = config
        self._context_builder = context_builder
        self._context: StrategyContext | None = None

    # ============================================================
    # 生命週期方法
    # ============================================================

    async def on_start(self, context: StrategyContext) -> None:
        """策略啟動時呼叫（可選覆寫）"""
        self._context = context

    async def on_stop(self) -> None:
        """策略停止時呼叫（可選覆寫）"""
        pass

    async def on_config_changed(self, new_config: dict[str, Any]) -> None:
        """配置變更時呼叫（可選覆寫）"""
        self._config = new_config

    # ============================================================
    # 核心方法（子類必須實作）
    # ============================================================

    @abstractmethod
    async def scan(self) -> list[Candidate]:
        """執行 Step 1~7，回傳候選清單"""
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        """驗證配置合法性"""
        ...

    @abstractmethod
    def get_default_config(self) -> dict[str, Any]:
        """回傳預設配置"""
        ...

    # ============================================================
    # 可選方法
    # ============================================================

    async def evaluate(self, candidate: Candidate) -> Signal | None:
        """對單一候選產生 Signal"""
        return None

    async def on_candidate_confirmed(
        self,
        candidate: Candidate,
        custom_tp: Decimal | None = None,
    ) -> Signal | None:
        """候選被人工確認後呼叫"""
        return await self.evaluate(candidate)

    # ============================================================
    # 輔助屬性
    # ============================================================

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @property
    def context(self) -> StrategyContext:
        if self._context is None:
            raise RuntimeError(f"Strategy {self.strategy_id} not started")
        return self._context

    def get_config(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
```

### 8.3.3 `StrategyContext` 類別（非規範摘要）

> `StrategyContext`、Clock 與所有時間/數值型別的唯一規範定義在 [Chapter 9 §9.3–§9.4](BLUEPRINT-PART05-Chapter09-10-StrategyPluginInterface.md) 及 Chapter 1 §1.4。本節不得重新宣告 `float`、wall-clock 或不同 timestamp 單位；只描述引擎使用方式。

```python
class StrategyContext:
    """策略執行上下文"""

    def __init__(
        self,
        clickhouse,
        redis,
        config,
        strategy_id: str,
    ):
        self._clickhouse = clickhouse
        self._redis = redis
        self._config = config
        self._strategy_id = strategy_id
        self._config_cache: dict = {}

    def now_ms(self) -> int:
        """僅為歷史摘錄；規範實作必須委派 Chapter 9 的 Clock。"""
        return self._clock.now_ms()

    async def get_config(self, key: str, default=None):
        if not self._config_cache:
            self._config_cache = await self._config.load_strategy_config(
                self._strategy_id,
            )
        return self._config_cache.get(key, default)

    async def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_ts: int | None = None,
    ) -> list:
        return await self._clickhouse.get_recent_klines(
            symbol, timeframe, limit, before_ts,
        )

    async def get_current_price(self, symbol: str):
        """按 5m → 1h → 4h → 1d 順序讀當前價"""
        for tf in ["5m", "1h", "4h", "1d"]:
            klines = await self._clickhouse.get_recent_klines(
                symbol, tf, 1,
            )
            if klines:
                return klines[-1].close
        return None

    async def get_all_symbols(self) -> list[str]:
        """讀取所有待監察 symbol"""
        cached = await self._redis.get("symbols:cache")
        if cached:
            return json.loads(cached)
        return []

    async def get_blacklist(self) -> set[str]:
        """讀取黑名單"""
        cached = await self._redis.hgetall("blacklist:cache")
        return set(cached.keys()) if cached else set()

    async def get_position(self, symbol: str) -> dict | None:
        data = await self._redis.hgetall(f"position:{symbol}")
        return data if data else None

    @property
    def strategy_id(self) -> str:
        return self._strategy_id
```

### 8.3.4 各 Step 類別介面（引用 Chapter 9）

> Step 的唯一輸入/輸出契約見 Chapter 9 §9.2.3；以下表格僅為引擎層引用，不得視為獨立定義。| Step   | 類別                        | 建構子        | 主要方法                    | 輸入                   | 輸出                    |
| ------ | --------------------------- | ------------- | --------------------------- | ---------------------- | ----------------------- |
| Step 1 | `Step1Scanner`            | `(context)` | `scan()`                  | 無                     | `list[str]`           |
| Step 2 | `Step2VolumeScanner`      | `(context)` | `scan(symbols)`           | `list[str]`          | `list[SpikeResult]`   |
| Step 3 | `Step3VolumeChecker`      | `(context)` | `check(spikes)`           | `list[SpikeResult]`  | `list[VolumeResult]`  |
| Step 4 | `Step4Phase1Detector`     | `(context)` | `detect(volumes)`         | `list[VolumeResult]` | `list[Phase1Result]`  |
| Step 5 | `Step5Phase2Detector`     | `(context)` | `detect(phase1s)`         | `list[Phase1Result]` | `list[Phase2Result]`  |
| Step 6 | `Step6SupportZoneChecker` | `(context)` | `check(phase2s)`          | `list[Phase2Result]` | `list[SupportResult]` |
| Step 7 | `Step7CandidateBuilder`   | `(context)` | `build(support)`          | `SupportResult`      | `Candidate \| None`    |
| Step 8 | `Step8Pricing`            | `(context)` | `build_signal(candidate)` | `Candidate`          | `Signal \| None`       |

 **注意** ：每個 Step 一個類別，遵守介面約定，但不強制繼承 `BaseStep`。

## 8.4 Layer 3：決策模式

### 8.4.1 三種模式

| 模式             | 逾時    | 行為                 |
| ---------------- | ------- | -------------------- |
| **MANUAL** | 無      | 只通知，等待手動進場 |
| **SEMI**   | 10 分鐘 | 逾時轉 AUTO          |
| **AUTO**   | —      | 直接進場             |

### 8.4.2 模式配置

**儲存在 MariaDB `strategies` 表** ：

```sql
SELECT id, mode FROM strategies WHERE id = 'volume_breakout_pullback_v1';
```

**可由 Telegram 切換** ：

```text
/set_strategy volume_breakout_pullback_v1 mode SEMI
```

### 8.4.3 `ModeHandler` 類別

> Candidate 狀態與 review lifecycle 以 Chapter 9/Chapter 12 canonical contract 為準。MANUAL 不進 pending review ZSET；只有 SEMI 的 `PENDING_REVIEW` 由 timeout worker 處理。Confirm、Reject 與 Timeout 必須共用 `lock:candidate:review:{trace_id}`（TTL 10s），取得鎖後再次檢查 `strategy:pending_review:active`，並以 Pipeline/Lua 原子移除 ZSET、active Set 與 Candidate Hash field。MariaDB terminal update 必須先於通知與 Redis ghost cleanup 的最終確認；重複 callback 不得再次執行 Step 8。

```python
class ModeHandler:
    """處理不同模式的候選流程"""

    def __init__(
        self,
        redis_client,
        publisher,
        engine: "StrategyEngine | None" = None,
        context: "StrategyContext | None" = None,
        config=None,
    ):
        self._redis = redis_client
        self._publisher = publisher
        self._engine = engine
        self._context = context
        self._config = config

    def set_engine(self, engine: "StrategyEngine") -> None:
        """由 StrategyEngine 在初始化後注入"""
        self._engine = engine

    def set_context(self, context: "StrategyContext") -> None:
        """由 StrategyEngine 在載入策略後注入"""
        self._context = context

    # ============================================================
    # 入口
    # ============================================================

    async def process(
        self,
        candidate: Candidate,
        mode: str,
    ) -> None:
        """依模式處理候選"""
        if mode == "MANUAL":
            await self._handle_manual(candidate)
        elif mode == "SEMI":
            await self._handle_semi(candidate)
        elif mode == "AUTO":
            await self._handle_auto(candidate)
        else:
            log.error("unknown_mode", mode=mode)

    # ============================================================
    # MANUAL 模式
    # ============================================================

    async def _handle_manual(self, candidate: Candidate) -> None:
        """MANUAL 模式：只通知，無逾時，等待使用者手動進場"""
        await self._redis.hset(
            "strategy:candidate_data",
            candidate.trace_id,
            candidate.model_dump_json(),
        )

        await self._publisher.publish(
            channel="telegram:send",
            event_type="telegram.candidate_notify",
            payload={
                "trace_id": candidate.trace_id,
                "mode": "MANUAL",
                "candidate": candidate.model_dump(),
            },
        )

    # ============================================================
    # 手動進場（含價格保護）
    # ============================================================

    async def _handle_manual_entry(
        self,
        candidate: Candidate,
    ) -> Signal | None:
        """處理手動進場（含價格保護）"""

        # 1. 讀取當前市價
        current_price = await self._context.get_current_price(candidate.symbol)
        if not current_price:
            raise PriceUnavailableError(candidate.symbol)

        # 2. 計算偏離率
        original_price = candidate.current_price
        deviation_pct = (
            abs(current_price - original_price) / original_price * 100
        )

        # 3. 讀取參數
        max_deviation = await self._config.get_typed(
            "manual_entry_max_deviation_pct", "Decimal",
        ) or 1.0

        # 4. 檢查
        if deviation_pct > max_deviation:
            log.warning(
                "manual_entry_price_deviation",
                symbol=candidate.symbol,
                deviation_pct=deviation_pct,
                max_deviation=max_deviation,
            )
            raise PriceDeviationError(
                f"價格已偏離觸發價 {deviation_pct:.2f}%，"
                f"超過上限 {max_deviation}%，為保護資金拒絕進場"
            )

        # 5. 通過 → 執行 Step 8
        if self._engine is None:
            raise RuntimeError("ModeHandler._engine not set")
        return await self._engine.execute_step8_pricing(candidate)

    # ============================================================
    # SEMI 模式
    # ============================================================

    async def _handle_semi(self, candidate: Candidate) -> None:
        """SEMI 模式：10 分鐘逾時轉 AUTO"""
        await self._redis.hset(
            "strategy:candidate_data",
            candidate.trace_id,
            candidate.model_dump_json(),
        )

        expire_at_ms = self._context.now_ms() + 10 * 60 * 1000
        await self._redis.zadd(
            "strategy:pending_reviews",
            {candidate.trace_id: expire_at_ms},
        )

        await self._redis.sadd(
            "strategy:pending_review:active",
            candidate.trace_id,
        )

        await self._publisher.publish(
            channel="telegram:send",
            event_type="telegram.candidate_notify",
            payload={
                "trace_id": candidate.trace_id,
                "mode": "SEMI",
                "candidate": candidate.model_dump(),
                "expire_at_ms": expire_at_ms,
            },
        )

    # ============================================================
    # AUTO 模式
    # ============================================================

    async def _handle_auto(self, candidate: Candidate) -> None:
        """AUTO 模式：直接進場"""
        candidate.status = "AUTO_APPROVED"

        if self._engine is None:
            log.error("auto_mode_no_engine", trace_id=candidate.trace_id)
            return

        await self._engine.execute_step8_pricing(candidate)

        await self._publisher.publish(
            channel="telegram:send",
            event_type="telegram.candidate_auto_approved",
            payload={
                "trace_id": candidate.trace_id,
                "candidate": candidate.model_dump(),
            },
        )
```

## 8.5 完整目錄結構

```text
ccurr-strategy/
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── models.py
    │
    ├── engine/
    │   ├── __init__.py
    │   ├── strategy_engine.py
    │   ├── plugin_loader.py
    │   ├── plugin_registry.py
    │   ├── context_builder.py
    │   ├── scheduler.py
    │   ├── task_runner.py
    │   ├── config_watcher.py
    │   └── health.py
    │
    ├── modes/
    │   ├── __init__.py
    │   ├── mode_handler.py
    │   ├── manual.py
    │   ├── semi.py
    │   └── auto.py
    │
    ├── review/
    │   ├── __init__.py
    │   ├── review_manager.py
    │   ├── timeout_loop.py
    │   └── custom_tp_handler.py
    │
    ├── plugins/
    │   ├── __init__.py
    │   ├── base_strategy.py
    │   ├── base_step.py
    │   ├── models.py
    │   ├── context.py
    │   ├── volume_breakout_pullback_v1.py
    │   └── steps/
    │       ├── __init__.py
    │       ├── step1_scanner.py
    │       ├── step2_volume_scanner.py
    │       ├── step3_volume_checker.py
    │       ├── step4_phase1_detector.py
    │       ├── step5_phase2_detector.py
    │       ├── step6_support_zone_checker.py
    │       ├── step7_candidate_builder.py
    │       └── step8_pricing.py
    │
    ├── http_api.py
    └── stats.py
```

## 8.6 `main.py` 啟動流程

```python
async def main_async():
    settings = StrategySettings()
    log = setup_logger(settings.service_name, settings.log_level)

    # 1. 基礎元件
    redis_client = await redis.asyncio.from_url(...)
    clickhouse_reader = ClickHouseReader(settings)
    await clickhouse_reader.connect()

    # 2. 通用機制
    trace_recorder = TraceRecorder(redis_client, settings.service_name)
    event_publisher = EventPublisher(redis_client, settings.service_name)
    audit_logger = AuditLogger(dbwriter_client, settings.service_name)
    degradation_reader = DegradationReader(redis_client)
    config_client = DynamicConfigClient(redis_client, dbwriter_client, "strategy")

    # 3. 策略引擎
    engine = StrategyEngine(
        settings=settings,
        clickhouse_reader=clickhouse_reader,
        redis_client=redis_client,
        config_client=config_client,
        dbwriter_client=dbwriter_client,
        trace_recorder=trace_recorder,
        event_publisher=event_publisher,
        audit_logger=audit_logger,
        degradation_reader=degradation_reader,
    )

    # 4. HTTP API（供 ccurr-telegram 呼叫）
    app = create_app(engine, settings)
    config = uvicorn.Config(app, uds=settings.uds_path, log_config=None)
    server = uvicorn.Server(config)

    # 5. 啟動
    heartbeat_task = asyncio.create_task(heartbeat_loop(redis_client, settings))
    await engine.start()

    log.info("strategy_started")
    await server.serve()

    # 6. 清理
    log.info("strategy_stopping")
    heartbeat_task.cancel()
    await engine.stop()
    await clickhouse_reader.close()
    await redis_client.close()
```

## 8.7 UDS API 端點

| Method | Path                        | 說明                           |
| ------ | --------------------------- | ------------------------------ |
| POST   | `/candidate/confirm`      | 使用者確認候選                 |
| POST   | `/candidate/reject`       | 使用者拒絕候選                 |
| POST   | `/candidate/manual_enter` | 手動進場（含價格保護，見 8.4.3） |
| GET    | `/strategy/list`          | 列出所有策略                   |
| GET    | `/strategy/{id}`          | 查策略詳情                     |
| GET    | `/strategy/{id}/config`   | 查策略配置                     |
| PUT    | `/strategy/{id}/config`   | 改策略配置                     |
| POST   | `/strategy/{id}/enable`   | 啟用策略                       |
| POST   | `/strategy/{id}/disable`  | 停用策略                       |
| POST   | `/strategy/reload`        | 重新載入所有策略               |
| GET    | `/candidates`             | 查詢候選清單                   |
| GET    | `/candidate/{trace_id}`   | 查單一候選                     |
| GET    | `/runs`                   | 查詢執行記錄                   |
| GET    | `/run/{run_id}`           | 查單次執行詳情                 |
| GET    | `/errors`                 | 查詢錯誤記錄                   |
| GET    | `/health`                 | 健康檢查                       |
| GET    | `/stats`                  | 統計                           |

### `POST /candidate/manual_enter` 規格

**Request body**：

```json
{
    "trace_id": "uuid-v4",
    "action": "MANUAL_ENTER"
}
```

**錯誤回應**：

```json
{
    "ok": false,
    "error": {
        "code": "PRICE_DEVIATION",
        "message": "價格已偏離觸發價 3.5%，超過上限 1.0%"
    }
}
```

**處理**：

1. 檢查 ZSET → `trace_id` 還在 pending
2. 從 `strategy:candidate_data` 讀取 Candidate
3. 呼叫 `ModeHandler._handle_manual_entry(candidate)`
4. 若拋出 `PriceDeviationError` → 回 `{ok: false, error: {...}}`
5. 成功 → 清理 ZSET + Hash，回傳 `{ok: true}`


---

## 8.8 關鍵設計決策

### 8.8.1 為什麼 Step 用類別

| 方案           | 優點                           | 缺點               |
| -------------- | ------------------------------ | ------------------ |
| **類別** | 可注入 Context、可測試、可組合 | 較多重複程式碼     |
| 函式           | 簡單                           | 難注入依賴、難測試 |

 **選擇** ：類別。每個 Step 一個類別，注入 `StrategyContext`。

 **優點** ：

* 改 Step 2 的放量公式 → 只改 `step2_volume_scanner.py`
* 獨立測試、獨立替換
* 記憶體內極速傳遞

### 8.8.2 為什麼策略插件要獨立檔案

| 原因               | 說明                 |
| ------------------ | -------------------- |
| **熱重載**   | 改一個策略不影響其他 |
| **版本控制** | 每個策略可獨立版控   |
| **團隊協作** | 不同人寫不同策略     |
| **回測**     | 可單獨測試每個策略   |

### 8.8.3 為什麼模式要獨立成 Layer 3

| 原因                       | 說明                     |
| -------------------------- | ------------------------ |
| **同一策略不同模式** | 回測用 AUTO，實盤用 SEMI |
| **可動態切換**       | Telegram 指令即時切換    |
| **關注點分離**       | 策略只管掃描，不管執行   |

### 8.8.4 為什麼 `scan()` 回傳 `Candidate` 而非 `Signal`

| 原因               | 說明                          |
| ------------------ | ----------------------------- |
| **人工確認** | SEMI 模式下需等待確認         |
| **模式分流** | AUTO 直接進 Signal，SEMI 等待 |
| **追蹤**     | Candidate 有獨立生命週期      |
| **審計**     | 記錄候選產生到確認的過程      |

### 8.8.5 為什麼 `Candidate` 用混合模型

| 方案           | 優點     | 缺點       |
| -------------- | -------- | ---------- |
| 全部 Pydantic  | 型別安全 | 難擴展     |
| 全部 dict      | 彈性     | 不安全     |
| **混合** | 兩者兼顧 | 需明確分層 |

 **選擇** ：基礎欄位 Pydantic，策略專屬資料用 `data: dict`。

### 8.8.6 為什麼配置熱重載用 Pub/Sub

| 方案              | 優點   | 缺點         |
| ----------------- | ------ | ------------ |
| 60 秒輪詢         | 簡單   | 最多等 60 秒 |
| **Pub/Sub** | 毫秒級 | 需訂閱       |

 **選擇** ：Pub/Sub。修改配置後 PUBLISH `config:changed`，容器訂閱後毫秒級生效。

### 8.8.7 為什麼序列執行

| 原因                          | 說明                 |
| ----------------------------- | -------------------- |
| **避免打爆 ClickHouse** | 並行會瞬間開多個連線 |
| **避免觸發幣安限流**    | 並行會同時發多個請求 |
| **目前只有 1 個策略**   | 序列執行幾秒鐘完成   |
| **未來 3 個策略也夠快** | 十幾秒可接受         |

 **選擇** ：序列執行。未來穩定運行半年後再考慮並行。

### 8.8.8 為什麼 `scan()` 超時 60 秒

| 原因                          | 說明                                 |
| ----------------------------- | ------------------------------------ |
| **正常應在 2~3 秒**     | 掃描只是讀 ClickHouse + 簡單數學比對 |
| **超過 60 秒 = 出大事** | 死鎖、斷線、無限迴圈                 |
| **防止拖死引擎**        | 一個壞策略不能拖死整個引擎           |

 **選擇** ：60 秒超時。超時則中斷該策略，發 critical 告警，繼續跑下一個。

---

## 第 8 章完成 ✅

 **已完成** ：

* 8.0 為什麼要三層架構
* 8.1 整體架構圖
* 8.2 Layer 1：策略引擎
* 8.3 Layer 2：策略插件
* 8.4 Layer 3：決策模式
* 8.5 完整目錄結構
* 8.6 `main.py` 啟動流程
* 8.7 UDS API 端點
* 8.8 關鍵設計決策

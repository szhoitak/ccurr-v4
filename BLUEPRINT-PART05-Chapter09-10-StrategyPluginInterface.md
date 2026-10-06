# 第 9 章：策略插件介面

> 本章定義策略插件的完整介面規格：`BaseStrategy` 抽象類、`BaseStep` 抽象類、資料模型、各 Step 類別介面、插件載入與熱重載。
>
> **契約權威（Strategy Plugin Contract v1）**：本章是 `BaseStrategy`、`BaseStep`、`StrategyContext`、`Candidate`、`Signal`、中間結果模型、`ContextBuilder`、插件載入/註冊，以及 live/backtest 共用策略生命週期的唯一規範來源。Chapter 7 只定義策略商業規則與 Step 語意；Chapter 8 只定義引擎編排與模式處理；Chapter 10 只定義本章契約的回測實作。其他章節若出現重複摘錄，只能作為非規範說明，不得覆寫本章。
>
> **版本與修訂**：本章契約目前為 `Strategy Plugin Contract v1`，隸屬 Blueprint `v4.0`（2026-09-28）。契約修訂必須記錄契約版本、日期、受影響介面、序列化/相容性影響及 migration 狀態；文件版本變更不自動代表 Python/API 契約變更。
>
> **共同生命週期**：`validate_config → strategy(config, context_builder) → context_builder.build(strategy_id) → on_start(context) → scan/evaluate → on_stop`。live 與 backtest 必須使用相同 constructor 與生命週期，只替換 ContextBuilder 注入的 clock、資料 provider、配置 provider 及持倉/執行 adapter。

---

## 9.0 整體架構

### 9.0.1 插件系統的分層

```text
┌─────────────────────────────────────────────────────────┐
│              ccurr-strategy 引擎層                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  StrategyEngine                                   │  │
│  │  ├── PluginLoader（載入插件）                      │  │
│  │  ├── PluginRegistry（註冊表）                      │  │
│  │  └── TaskRunner（執行 + 60s 超時）                 │  │
│  └───────────────────────────────────────────────────┘  │
│                          │                               │
│                          ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │  插件介面層（本章）                                │  │
│  │  ├── BaseStrategy（抽象類）                        │  │
│  │  ├── BaseStep（抽象類，可選）                      │  │
│  │  ├── StrategyContext（上下文）                     │  │
│  │  ├── Candidate（候選模型）                         │  │
│  │  └── Signal（信號模型）                            │  │
│  └───────────────────────────────────────────────────┘  │
│                          │                               │
│                          ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │  具體策略層                                        │  │
│  │  └── VolumeBreakoutPullbackV1                     │  │
│  │      ├── Step1Scanner                             │  │
│  │      ├── Step2VolumeScanner                       │  │
│  │      ├── ...                                      │  │
│  │      └── Step8Pricing                             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 9.0.2 檔案結構

```text
ccurr-strategy/app/plugins/
├── __init__.py
├── base_strategy.py          # BaseStrategy 抽象類
├── base_step.py              # BaseStep 抽象類（可選）
├── models.py                 # Candidate, Signal, 中間模型
├── context.py                # StrategyContext
├── volume_breakout_pullback_v1.py   # 具體策略
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

## 9.1 BaseStrategy 抽象類

### 9.1.1 完整定義

```python

# plugins/base_strategy.py

from abc import ABC, abstractmethod
from typing import Any
from plugins.context import StrategyContext
from plugins.models import Candidate, Signal

class BaseStrategy(ABC):
    """所有策略的抽象基底類別

    子類必須定義：
    - 類別屬性：strategy_id, strategy_name, version
    - scan()：執行 Step 1~7，回傳候選清單
    - validate_config()：驗證配置合法性
    - get_default_config()：回傳預設配置

    子類可選：
    - on_start()：策略啟動時初始化
    - on_stop()：策略停止時清理
    - on_config_changed()：配置變更時更新
    - evaluate()：對單一候選產生 Signal
    - on_candidate_confirmed()：候選被確認後產生 Signal
    """

    # ============================================================
    # 類別屬性（子類必須覆寫）
    # ============================================================

    strategy_id: str = ""
    """策略唯一識別碼，snake_case，例如 "volume_breakout_pullback_v1" """

    strategy_name: str = ""
    """策略人類可讀名稱，例如 "Volume Breakout Pullback" """

    version: str = "1.0"
    """策略版本，例如 "1.0" """

    description: str = ""
    """策略說明（可選）"""

    # ============================================================
    # 建構子
    # ============================================================

    def __init__(
        self,
        config: dict[str, Any],
        context_builder: "ContextBuilder",
    ):
        """初始化策略。

        唯一規範建構子：live 與 backtest 都傳入 ContextBuilder，
        不得直接傳入已建立的 StrategyContext。
        """
        self._config = config
        self._context_builder = context_builder
        self._context: StrategyContext | None = None

    # ============================================================
    # 生命週期方法
    # ============================================================

    async def on_start(self, context: StrategyContext) -> None:
        """策略啟動時呼叫（可選覆寫）

        用途：
        - 初始化 Step 實例
        - 載入快取資料
        - 建立資料庫連線
        """
        self._context = context

    async def on_stop(self) -> None:
        """策略停止時呼叫（可選覆寫）

        用途：
        - 清理資源
        - 關閉連線
        - 儲存狀態
        """
        pass

    async def on_config_changed(self, new_config: dict[str, Any]) -> None:
        """配置變更時呼叫（可選覆寫）

        Args:
            new_config: 新的配置 dict
        """
        self._config = new_config

    # ============================================================
    # 核心方法（子類必須實作）
    # ============================================================

    @abstractmethod
    async def scan(self) -> list[Candidate]:
        """執行 Step 1~7，回傳候選清單

        這是策略的主入口。引擎會定時呼叫此方法（預設每 15 分鐘）。

        注意：
        - 執行時間上限 60 秒（由 TaskRunner 控制）
        - 內部應執行 Step 1~7，依序篩選
        - 回傳的 Candidate 尚未經人工確認

        Returns:
            list[Candidate]：通過所有篩選的候選清單
        """
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        """驗證配置合法性

        由 PluginLoader 在載入時呼叫。

        Returns:
            True：配置合法
            False：配置不合法（策略不會被載入）
        """
        ...

    @abstractmethod
    def get_default_config(self) -> dict[str, Any]:
        """回傳預設配置

        用途：
        - 首次載入時寫入 MariaDB
        - 配置缺失時作為 fallback

        Returns:
            dict：預設配置
        """
        ...

    # ============================================================
    # 可選方法（子類可覆寫）
    # ============================================================

    async def evaluate(self, candidate: Candidate) -> Signal | None:
        """對單一候選產生 Signal（可選覆寫）

        用途：
        - AUTO 模式下直接產生 Signal
        - 若未覆寫，回傳 None（表示不自動產生）

        Args:
            candidate: 候選物件

        Returns:
            Signal 或 None
        """
        return None

    async def on_candidate_confirmed(
        self,
        candidate: Candidate,
        custom_tp: Decimal | None = None,
    ) -> Signal | None:
        """候選被人工確認後呼叫（可選覆寫）

        用途：
        - SEMI / MANUAL 模式下，使用者確認後執行 Step 8
        - 預設實作：呼叫 evaluate()

        Args:
            candidate: 候選物件
            custom_tp: 自訂停利價（可選）

        Returns:
            Signal 或 None
        """
        return await self.evaluate(candidate)

    # ============================================================
    # 輔助屬性
    # ============================================================

    @property
    def config(self) -> dict[str, Any]:
        """當前配置"""
        return self._config

    @property
    def context(self) -> StrategyContext:
        """執行上下文"""
        if self._context is None:
            raise RuntimeError(
                f"Strategy {self.strategy_id} not started. "
                "Call on_start() first."
            )
        return self._context

    def get_config(self, key: str, default: Any = None) -> Any:
        """讀取配置項（含預設值）"""
        return self._config.get(key, default)
```

### 9.1.2 子類實作範例

```python
# plugins/volume_breakout_pullback_v1.py

from plugins.base_strategy import BaseStrategy
from plugins.models import Candidate, Signal
from plugins.steps import (
    Step1Scanner,
    Step2VolumeScanner,
    Step3VolumeChecker,
    Step4Phase1Detector,
    Step5Phase2Detector,
    Step6SupportZoneChecker,
    Step7CandidateBuilder,
    Step8Pricing,
)

class VolumeBreakoutPullbackV1(BaseStrategy):
    """帶量突破回踩策略"""

    strategy_id = "volume_breakout_pullback_v1"
    strategy_name = "Volume Breakout Pullback"
    version = "1.0"
    description = "捕捉帶量突破後的縮量回踩"

    async def on_start(self, context) -> None:
        await super().on_start(context)

        # 初始化各 Step
        self._step1 = Step1Scanner(context)
        self._step2 = Step2VolumeScanner(context)
        self._step3 = Step3VolumeChecker(context)
        self._step4 = Step4Phase1Detector(context)
        self._step5 = Step5Phase2Detector(context)
        self._step6 = Step6SupportZoneChecker(context)
        self._step7 = Step7CandidateBuilder(context)
        self._step8 = Step8Pricing(context)

    async def scan(self) -> list[Candidate]:
        """執行 Step 1~7"""
        candidates = []

        # Step 1：掃描全市貨幣
        symbols = await self._step1.scan()
        log.info("step1_done", count=len(symbols))

        if not symbols:
            return []

        # Step 2：放量掃描
        spike_results = await self._step2.scan(symbols)
        log.info("step2_done", count=len(spike_results))

        if not spike_results:
            return []

        # Step 3：成交額檢查
        volume_results = await self._step3.check(spike_results)
        log.info("step3_done", count=len(volume_results))

        if not volume_results:
            return []

        # Step 4：Phase 1 升幅期
        phase1_results = await self._step4.detect(volume_results)
        log.info("step4_done", count=len(phase1_results))

        if not phase1_results:
            return []

        # Step 5：Phase 2 回踩期
        phase2_results = await self._step5.detect(phase1_results)
        log.info("step5_done", count=len(phase2_results))

        if not phase2_results:
            return []

        # Step 6：接近低價區
        support_results = await self._step6.check(phase2_results)
        log.info("step6_done", count=len(support_results))

        if not support_results:
            return []

        # Step 7：產生候選
        for support_data in support_results:
            candidate = await self._step7.build(support_data)
            if candidate:
                candidates.append(candidate)

        log.info("step7_done", count=len(candidates))
        return candidates

    async def evaluate(self, candidate: Candidate) -> Signal | None:
        """Step 8：計算掛單價，產生 Signal"""
        return await self._step8.build_signal(candidate)

    def validate_config(self) -> bool:
        """驗證配置"""
        required_keys = [
            "threshold_ma7",
            "threshold_ma20",
            "min_volume_24h_usdt",
            "phase1_min_rise_pct",
            "phase2_min_drawdown_pct",
            "phase6_tolerance_pct",
        ]

        for key in required_keys:
            if key not in self._config:
                log.error("missing_config_key",
                         strategy_id=self.strategy_id,
                         key=key)
                return False

        return True

    def get_default_config(self) -> dict:
        """預設配置"""
        return {
            # Step 2
            "threshold_ma7": 3.0,
            "threshold_ma20": 2.0,
            # Step 3
            "min_volume_24h_usdt": 3000000,
            # Step 4
            "phase1_min_rise_pct": 15.0,
            # Step 5
            "phase2_min_drawdown_pct": 5.0,
            # Step 6
            "phase6_tolerance_pct": 3.0,
            # ...
        }
```

## 9.2 `BaseStep` 抽象類（可選）

### 9.2.1 為什麼提供但不強制

Step 類別不強制繼承共同基底，但提供一個 `BaseStep` 可選基底，讓共用邏輯（如日誌、追蹤）可集中。

### 9.2.2 完整定義

```python
# plugins/base_step.py

from abc import ABC
from plugins.context import StrategyContext

class BaseStep(ABC):
    """Step 抽象基底（可選）

    子類可自由實作 run() 方法，不強制統一名稱。
    此基底只提供共用屬性。
    """

    step_id: str = ""
    """Step 識別碼，例如 "step2" """

    step_name: str = ""
    """Step 名稱，例如 "Volume Scanner" """

    def __init__(self, context: StrategyContext):
        self._context = context

    @property
    def context(self) -> StrategyContext:
        return self._context

    def now_ms(self) -> int:
        """當前時間；實作必須委派給 StrategyContext 的 Clock。"""
        return self._context.now_ms()
```

### 9.2.3 各 Step 的介面約定

每個 Step 類別 **不需強制繼承 BaseStep** ，但必須遵守以下介面約定：

| Step   | 類別名稱                    | 建構子        | 主要方法                    | 輸入                   | 輸出                    |
| ------ | --------------------------- | ------------- | --------------------------- | ---------------------- | ----------------------- |
| Step 1 | `Step1Scanner`            | `(context)` | `scan()`                  | 無                     | `list[str]`           |
| Step 2 | `Step2VolumeScanner`      | `(context)` | `scan(symbols)`           | `list[str]`          | `list[SpikeResult]`   |
| Step 3 | `Step3VolumeChecker`      | `(context)` | `check(spikes)`           | `list[SpikeResult]`  | `list[VolumeResult]`  |
| Step 4 | `Step4Phase1Detector`     | `(context)` | `detect(volumes)`         | `list[VolumeResult]` | `list[Phase1Result]`  |
| Step 5 | `Step5Phase2Detector`     | `(context)` | `detect(phase1s)`         | `list[Phase1Result]` | `list[Phase2Result]`  |
| Step 6 | `Step6SupportZoneChecker` | `(context)` | `check(phase2s)`          | `list[Phase2Result]` | `list[SupportResult]` |
| Step 7 | `Step7CandidateBuilder`   | `(context)` | `build(support)`          | `SupportResult`      | `Candidate \| None`    |
| Step 8 | `Step8Pricing`            | `(context)` | `build_signal(candidate)` | `Candidate`          | `Signal \| None`       |

---

## 9.3 `StrategyContext` 介面

> **Canonical context contract**：live 與 backtest 必須提供相同的策略可見方法。建構子依賴名稱固定為 `clickhouse_reader`、`redis_client`、`config_client`、`strategy_id`；執行環境差異透過注入的 `Clock`、provider 與 adapter 實現，不得另行建立第二套 Context API。
>
> `Clock` 至少提供 `now_ms() -> int`。live 使用 `SystemClock`，backtest 使用 `VirtualClock`。策略與 Step 不得直接呼叫 `time.time()`、全域 `now_ms()` 或其他 wall-clock helper。

### 9.3.1 完整定義

```python
# plugins/context.py

from typing import Any, Protocol
from decimal import Decimal


class Clock(Protocol):
    """策略唯一可見的時間來源。"""

    def now_ms(self) -> int:
        ...


class StrategyContext:
    """策略執行上下文

    提供策略存取外部資源的統一介面：
    - ClickHouse（K 線）
    - Redis（快取、狀態）
    - Config（動態配置）
    - Clock（live 或 backtest 時間）
    """

    def __init__(
        self,
        clickhouse_reader,
        redis_client,
        config_client,
        strategy_id: str,
        clock: Clock,
    ):
        self._clickhouse = clickhouse_reader
        self._redis = redis_client
        self._config = config_client
        self._strategy_id = strategy_id
        self._clock = clock
        self._config_cache: dict[str, Any] = {}

    # ============================================================
    # 時間（回測時會被覆寫）
    # ============================================================

    def now_ms(self) -> int:
        """當前時間（毫秒），由注入的 Clock 提供。"""
        return self._clock.now_ms()

    # ============================================================
    # 配置讀取
    # ============================================================

    async def get_config(self, key: str, default: Any = None) -> Any:
        """讀取策略配置（含快取）"""
        if not self._config_cache:
            self._config_cache = await self._config.load_strategy_config(
                self._strategy_id,
            )
        return self._config_cache.get(key, default)

    async def reload_config(self) -> None:
        """強制重新載入配置"""
        self._config_cache = await self._config.load_strategy_config(
            self._strategy_id,
        )

    # ============================================================
    # ClickHouse 讀取
    # ============================================================

    async def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_ts: int | None = None,
    ) -> list:
        """讀取 K 線（含指標）"""
        return await self._clickhouse.get_recent_klines(
            symbol, timeframe, limit, before_ts,
        )

    async def get_current_price(self, symbol: str) -> Decimal | None:
        """按 5m → 1h → 4h → 1d 順序讀取當前價"""
        for tf in ["5m", "1h", "4h", "1d"]:
            klines = await self._clickhouse.get_recent_klines(
                symbol, tf, 1,
            )
            if klines:
                return klines[-1].close
        return None

    # ============================================================
    # MariaDB 讀取（透過快取）
    # ============================================================

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

    # ============================================================
    # Redis 讀取
    # ============================================================

    async def get_position(self, symbol: str) -> dict | None:
        """讀取持倉"""
        data = await self._redis.hgetall(f"position:{symbol}")
        return data if data else None

    async def get_all_positions(self) -> dict[str, dict]:
        """讀取所有持倉"""
        positions = {}
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor,
                match="position:*",
                count=100,
            )
            for key in keys:
                symbol = key.split(":", 1)[1]
                positions[symbol] = await self._redis.hgetall(key)
            if cursor == 0:
                break
        return positions

    # ============================================================
    # 輔助工具
    # ============================================================

    @property
    def strategy_id(self) -> str:
        return self._strategy_id
```

### 9.4 資料模型

> **數值與時間契約**：所有價格、數量、金額、成交量、百分比與 RVOL 欄位使用 `Decimal`，禁止 Python `float`。欄位名稱含 `_pct` 時採百分比點語意（`Decimal("5.0")` = 5%）；RVOL/ratio 是無單位倍數。所有 `*_ms` timestamp 為 UTC epoch milliseconds `int`，並須通過 13 位毫秒驗證。JSON/Redis 序列化必須保留 Decimal 語意，不得隱式轉成 float。

#### 9.4.1 Candidate（候選）

```python
# plugins/models.py

from pydantic import BaseModel, Field
from decimal import Decimal

class Candidate(BaseModel):
    """策略產生的候選

    設計原則：
    - 基礎欄位用 Pydantic 鎖死 → Telegram / Executor 不會因缺欄位 Crash
    - 策略專屬資料用 data: dict → 保持彈性
    """

    # === 基礎欄位（Pydantic 鎖死）===
    symbol: str
    strategy_id: str
    trace_id: str
    generated_at_ms: int  # UTC epoch milliseconds, validated as 13-digit int
    status: str = "PENDING_REVIEW"
    # Allowed: PENDING_REVIEW, AUTO_APPROVED, CONFIRMED, REJECTED,
    # TIMEOUT_AUTO, TIMEOUT_CANCEL, CANCELED,
    # MANUAL_PRICE_DEVIATION_REJECT
    review_action: str | None = None
    review_responded_at_ms: int | None = None
    custom_tp: Decimal | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            "CONFIRMED",
            "REJECTED",
            "MANUAL_PRICE_DEVIATION_REJECT",
            "TIMEOUT_AUTO",
            "TIMEOUT_CANCEL",
        }
    score: Decimal = Decimal("0.0")  # Decimal; no float
    current_price: Decimal | None = None
    support_type: str | None = None        # S_R_FLIP / ORIGIN_LOW
    support_target_price: Decimal | None = None
    origin_low: Decimal | None = None
    peak_high: Decimal | None = None
    previous_range_high: Decimal | None = None
    drawdown_pct: Decimal | None = None
    profit_potential_pct: Decimal | None = None

    # === 策略專屬資料（彈性 dict）===
    data: dict = Field(default_factory=dict)

    # === 審核相關 ===
    review_deadline_ms: int | None = None

```

### 9.4.2 `Signal`（信號）

```python
class Signal(BaseModel):
    """交易信號"""

    signalId: str
    traceId: str
    strategyId: str
    timestamp_ms: int  # UTC epoch milliseconds, validated as 13-digit int
    symbol: str
    action: str = "OPEN_LONG"
    weight_pct: Decimal  # percentage points; Decimal("10.0") means 10%

    plan: dict = Field(default_factory=dict)
    """交易計畫：
    {
        "entry": {"type": "LIMIT", "price": ...},
        "take_profit": {"type": "LIMIT_MAKER", "price": ...},
        "stop_loss": {
            "type": "STOP_LOSS_LIMIT",
            "stop_price": ...,
            "stop_limit_price": ...,
        },
    }
    """

    metadata: dict = Field(default_factory=dict)
```

### 9.4.3 Order Intent Contract（Spot）

> `Signal.plan` 是 live 與 backtest 共用的上游交易意圖；它不是 Binance request。`ccurr-risk` 將意圖核算為可下單數量，`ccurr-executor` 將其轉為 `OrderIntent`，`ccurr-trader` 才負責 Spot REST 傳輸。BacktestEngine 使用同一份 `OrderIntent` 交給 MockBroker；策略插件不得判斷 live/backtest，也不得直接呼叫 Binance。

```python
class OrderIntent(BaseModel):
    """產品中立但 Spot-only 的單一訂單意圖。"""
    symbol: str
    strategy_id: str
    trace_id: str
    signal_id: str
    client_order_id: str
    side: str                    # BUY / SELL
    order_type: str              # LIMIT / MARKET（Spot；OTO/OTOCO working 只允許 LIMIT）
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str = "GTC"


class OtoOrderIntent(BaseModel):
    """Spot OTO/OTOCO 的三段意圖；pending quantity 與 entry 分開。"""
    list_client_order_id: str
    entry: OrderIntent
    pending_quantity: Decimal
    take_profit: OrderIntent | None = None
    stop_loss: OrderIntent | None = None


class OrderIdentity(BaseModel):
    """內部與交易所 ID 的責任分界。"""
    trace_id: str
    signal_id: str
    client_order_id: str          # 我方唯一冪等鍵，由 ccurr-executor 產生
    exchange_order_id: str | None = None
    order_list_id: str | None = None
```

**Spot-only 規則：**本系統不支援 Futures/Margin；不得使用 `reduceOnly`。`client_order_id` 格式為 `{strategy_id}-{uuid4}`，retry 必須重用同一值；`exchange_order_id` 與 `order_list_id` 由 Binance 回傳，不得作為我方冪等鍵。

**Order List 語意：** OCO 是同時啟用的 TP/SL 二選一；OTO 是 working Entry 完全成交後啟用一個 pending order；OTOCO 是 working Entry 完全成交後啟用 TP/SL OCO。Partial Fill 不會觸發 pending order。原子 OTOCO 不可用時，fallback 必須明確標記為 `Entry + post-fill OCO`，不得稱為原子 OTOCO。

**Quantity 規則：** 原子 OTO/OTOCO 使用 `pending_quantity`；fallback OCO 使用實際 `executed_qty`，必要時扣除非 BNB 手續費預留量，再依 symbol filters 截斷。`executed_qty <= 0`、低於最小數量或低於最小名義價值時不得送出 OCO，必須進入告警/人工處理狀態。

---

### 9.4.5 RiskResult / RiskCalculator Contract

```python
class RiskResult(BaseModel):
    allowed: bool
    calculated_qty: Decimal | None = None
    risk_amount: Decimal | None = None
    actual_risk_pct: Decimal | None = None
    notional: Decimal | None = None
    rejection_reason: str | None = None
    rule_id: str | None = None       # R06/R12/R13/R14/R17
    fee_mode: str                   # BNB / NON_BNB
    risk_version: str = "V1"


class RiskCalculator(Protocol):
    async def check(
        self,
        signal: Signal,
        account: AccountSnapshot,
        symbol_filters: SymbolFilters,
        fee_mode: str,
    ) -> RiskResult:
        """Live ccurr-risk 與 Backtest 必須共用的 V1 商業契約。"""
        ...
```

**V1 規則**：`weight_pct` 是資金權重；R17 先算 allocation quantity，R06 以 `entry_price - stop_limit_price` 與雙向費用作最高優先 DENY，R12 向下截斷後只重跑 R14，R13 檢查 free USDT。`MIN_NOTIONAL_REJECT`、`INSUFFICIENT_BALANCE` 與一般 `RISK_REJECTED` 都必須保留 rule_id/rejection_reason。Backtest 不得建立另一套 `_calc_qty` 語意。

```python
class SpikeObservation(BaseModel):
    """Step 2 單一 timeframe 觀測；所有數值均為 Decimal。"""
    timeframe: str                     # 1d / 4h / 1h
    slot_ts: int                       # UTC K 線開盤時間，13 位毫秒
    current_volume_quote: Decimal
    ma7: Decimal | None = None
    ma20: Decimal | None = None
    rvol_ma7: Decimal | None = None    # 無單位倍數
    rvol_ma20: Decimal | None = None   # 無單位倍數
    is_closed: bool
    elapsed_ms: int | None = None      # context.now_ms() - slot_ts
    is_spike: bool = False


class SpikeResult(BaseModel):
    """Step 2 輸出；唯一 canonical typed model。"""
    symbol: str
    observations: list[SpikeObservation]
    spike_timeframes: list[str]
    is_conflict: bool = False


class VolumeResult(BaseModel):
    """Step 3 輸出"""
    symbol: str
    spike_timeframes: list[str]
    volume_24h: Decimal
    volume_samples: int


class Phase1Result(BaseModel):
    """Step 4 輸出"""
    symbol: str
    origin_low: Decimal
    peak_high: Decimal
    peak_timestamp_ms: int  # UTC epoch milliseconds
    previous_range_high_4h: Decimal
    rise_pct: Decimal  # percentage points
    max_1h_rvol: Decimal  # unitless multiple


class Phase2Result(BaseModel):
    """Step 5 輸出"""
    symbol: str
    peak_high: Decimal
    origin_low: Decimal
    previous_range_high_4h: Decimal
    current_price: Decimal
    drawdown_pct: Decimal  # percentage points
    peak_timestamp_ms: int  # UTC epoch milliseconds
    phase2_detected_at: int  # UTC epoch milliseconds


class SupportResult(BaseModel):
    """Step 6 輸出"""
    symbol: str
    support_type: str                      # S_R_FLIP / ORIGIN_LOW
    support_target_price: Decimal
    current_price: Decimal
    origin_low: Decimal
    peak_high: Decimal
    previous_range_high: Decimal
    drawdown_pct: Decimal  # percentage points```

## 9.5 各 Step 類別介面規格

### 9.5.1 `Step1Scanner`

```python
class Step1Scanner(BaseStep):
    """Step 1：掃描全市貨幣（排除黑名單）"""

    step_id = "step1"
    step_name = "Symbol Scanner"

    def __init__(self, context: StrategyContext):
        super().__init__(context)
        self._symbols_cache: list[str] = []
        self._cache_ts: int = 0

    async def scan(self) -> list[str]:
        """回傳待監察 symbol 清單

        Returns:
            list[str]：排除黑名單後的 symbol 清單
        """
        ...
```

### 9.5.2 `Step2VolumeScanner`

```python
class Step2VolumeScanner(BaseStep):
    """Step 2：放量掃描（同槽位對比）"""

    step_id = "step2"
    step_name = "Volume Scanner"

    async def scan(self, symbols: list[str]) -> list[SpikeResult]:
        """對每個 symbol 檢查放量

        Args:
            symbols: Step 1 的輸出

        Returns:
            list[SpikeResult]：有放量的 symbol
        """
        ...

    async def _check_symbol(self, symbol: str) -> SpikeResult | None:
        """檢查單一 symbol"""
        ...

    async def _check_1d(self, symbol: str) -> SpikeObservation | None:
        """1d 放量檢查（不年化）"""
        ...

    async def _check_4h(self, symbol: str) -> SpikeObservation | None:
        """4h 同槽位放量檢查"""
        ...

    async def _check_1h(self, symbol: str) -> SpikeObservation | None:
        """1h 同槽位放量檢查"""
        ...
```

### 9.5.3 `Step3VolumeChecker`

```python
class Step3VolumeChecker(BaseStep):
    """Step 3：成交額檢查"""

    step_id = "step3"
    step_name = "Volume Checker"

    async def check(
        self,
        spikes: list[SpikeResult],
    ) -> list[VolumeResult]:
        """檢查近 24h 成交量

        Args:
            spikes: Step 2 的輸出

        Returns:
            list[VolumeResult]：通過檢查的 symbol
        """
        ...
```

### 9.5.4 `Step4Phase1Detector`

```python
class Step4Phase1Detector(BaseStep):
    """Step 4：Phase 1 升幅期偵測"""

    step_id = "step4"
    step_name = "Phase 1 Detector"

    async def detect(
        self,
        volumes: list[VolumeResult],
    ) -> list[Phase1Result]:
        """偵測 Phase 1

        Args:
            volumes: Step 3 的輸出

        Returns:
            list[Phase1Result]：通過 Phase 1 的 symbol
        """
        ...

    async def _check_1d_macro(self, symbol: str) -> bool:
        """條件 1：1d 宏觀保障"""
        ...

    async def _check_4h_momentum(self, symbol: str) -> dict | None:
        """條件 2：4h 核心動能"""
        ...

    async def _check_1h_trigger(self, symbol: str) -> bool:
        """條件 3：1h 爆發確認"""
        ...

    async def _calc_previous_range_high(
        self, symbol: str, origin_low_ts: int,
    ) -> Decimal | None:
        """計算 previous_range_high_4h"""
        ...

    async def _save_phase1_anchor(self, result: Phase1Result) -> None:
        """儲存 Phase 1 錨點到 Redis"""
        ...
```

### 9.5.5 `Step5Phase2Detector`

```python
class Step5Phase2Detector(BaseStep):
    """Step 5：Phase 2 回踩期偵測"""

    step_id = "step5"
    step_name = "Phase 2 Detector"

    async def detect(
        self,
        phase1s: list[Phase1Result],
    ) -> list[Phase2Result]:
        """偵測 Phase 2

        Args:
            phase1s: Step 4 的輸出

        Returns:
            list[Phase2Result]：通過 Phase 2 的 symbol
        """
        ...

    async def _check_1d_gatekeeper(self, symbol: str) -> bool:
        """1d 守門員：是否破底"""
        ...

    async def _check_4h_gatekeeper(self, symbol: str) -> bool:
        """4h 守門員：是否連續倒貨"""
        ...

    async def _check_price_behavior(
        self, symbol: str, phase1: Phase1Result,
    ) -> dict | None:
        """條件 2：價格行為"""
        ...

    async def _check_volume_behavior(
        self, symbol: str, phase1: Phase1Result,
    ) -> bool:
        """條件 3：縮量檢查"""
        ...

    async def _cleanup_if_broke_origin(
        self, symbol: str, current_close: Decimal, origin_low: Decimal,
    ) -> bool:
        """若跌破 origin_low，清理 Redis"""
        ...
```

### 9.5.6 `Step6SupportZoneChecker`

```python
class Step6SupportZoneChecker(BaseStep):
    """Step 6：接近低價區檢查"""

    step_id = "step6"
    step_name = "Support Zone Checker"

    async def check(
        self,
        phase2s: list[Phase2Result],
    ) -> list[SupportResult]:
        """檢查是否接近低價區

        Args:
            phase2s: Step 5 的輸出

        Returns:
            list[SupportResult]：接近低價區的 symbol
        """
        ...

    async def _check_sr_flip(
        self, phase2: Phase2Result,
    ) -> SupportResult | None:
        """檢查 A 區（S/R Flip）"""
        ...

    async def _check_origin_low(
        self, phase2: Phase2Result,
    ) -> SupportResult | None:
        """檢查 B 區（Origin Low）"""
        ...
```

### 9.5.7 `Step7CandidateBuilder`

```python

class Step7CandidateBuilder(BaseStep):
    """Step 7：產生候選名單"""

    step_id = "step7"
    step_name = "Candidate Builder"

    async def build(
        self,
        support: SupportResult,
    ) -> Candidate | None:
        """產生 Candidate

        處理：
        1. 檢查冷卻
        2. 計算 profit_potential_pct
        3. 過濾利潤空間
        4. 產生 trace_id
        5. 寫入 Redis（依模式分流）

        Args:
            support: Step 6 的輸出

        Returns:
            Candidate 或 None（若冷卻中或利潤不足）
        """
        ...

    async def _check_cooldown(self, symbol: str) -> bool:
        """檢查冷卻"""
        ...

    async def _set_cooldown(self, symbol: str, trace_id: str) -> None:
        """設定冷卻"""
        ...

    async def _dispatch_by_mode(
        self, candidate: Candidate, mode: str,
    ) -> None:
        """依模式分流"""
        ...
```

### 9.5.8 Step8Pricing

```python
class Step8Pricing(BaseStep):
    """Step 8：計算掛單價 + OTOCO 交易計畫"""

    step_id = "step8"
    step_name = "Pricing"

    async def build_signal(
        self,
        candidate: Candidate,
        custom_tp: Decimal | None = None,
    ) -> Signal | None:
        """產生 Signal

        處理：
        1. 計算進場價（永遠 LIMIT）
        2. 計算停損價
        3. 計算停利價（可被 custom_tp 覆蓋）
        4. 計算資金權重
        5. 打包 Signal
        6. 發布到 Redis

        Args:
            candidate: 候選物件
            custom_tp: 自訂停利價（可選）

        Returns:
            Signal 或 None
        """
        ...

    async def _calc_entry(
        self, candidate: Candidate,
    ) -> dict:
        """計算進場價"""
        ...

    async def _calc_stop_loss(
        self, candidate: Candidate,
    ) -> dict:
        """計算停損價"""
        ...

    async def _calc_take_profit(
        self,
        candidate: Candidate,
        custom_tp: Decimal | None,
    ) -> dict:
        """計算停利價"""
        ...

    async def _calc_weight(
        self, support_type: str,
    ) -> Decimal:
        """計算資金權重（百分比點，Decimal）。"""
        ...
```

## 9.6 插件註冊與載入

### 9.6.1 `PluginRegistry`

```python
class PluginRegistry:
    """插件註冊表"""

    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, strategy_id: str, strategy: BaseStrategy) -> None:
        """註冊策略"""
        self._strategies[strategy_id] = strategy

    def unregister(self, strategy_id: str) -> None:
        """取消註冊"""
        self._strategies.pop(strategy_id, None)

    def get(self, strategy_id: str) -> BaseStrategy | None:
        """取得策略"""
        return self._strategies.get(strategy_id)

    def list_all(self) -> dict[str, BaseStrategy]:
        """列出所有策略"""
        return dict(self._strategies)

    def list_ids(self) -> list[str]:
        """列出所有策略 ID"""
        return list(self._strategies.keys())
```

### 9.6.2 `PluginLoader`

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
        """判斷是否為策略檔案"""
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

---

## 9.7 完整策略實作範例

### 9.7.1 目錄結構

```text
ccurr-strategy/app/plugins/
├── __init__.py
├── base_strategy.py
├── base_step.py
├── models.py
├── context.py
├── volume_breakout_pullback_v1.py    # 主策略
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

### 9.7.2 Step 類別骨架範例

```python
# plugins/steps/step1_scanner.py

from plugins.base_step import BaseStep
from plugins.context import StrategyContext

class Step1Scanner(BaseStep):
    """Step 1：掃描全市貨幣（排除黑名單）"""

    step_id = "step1"
    step_name = "Symbol Scanner"

    def __init__(self, context: StrategyContext):
        super().__init__(context)
        self._symbols_cache: list[str] = []
        self._cache_ts: int = 0
        self._cache_ttl_ms: int = 300 * 1000  # 5 分鐘

    async def scan(self) -> list[str]:
        """回傳待監察 symbol 清單"""
        now = self.now_ms()

        # 快取檢查
        if self._symbols_cache and (now - self._cache_ts) < self._cache_ttl_ms:
            return self._symbols_cache

        # 1. 讀取所有 symbol
        all_symbols = await self.context.get_all_symbols()

        # 2. 讀取黑名單
        blacklist = await self.context.get_blacklist()

        # 3. 過濾
        result = [s for s in all_symbols if s not in blacklist]

        # 4. 更新快取
        self._symbols_cache = result
        self._cache_ts = now

        return result
```

### 9.7.3 新增策略的步驟

 **新增一個策略只需** ：

1. 在 `plugins/` 新增一個檔案（例如 `ma_cross_v1.py`）
2. 繼承 `BaseStrategy`
3. 定義 `strategy_id` / `strategy_name` / `version`
4. 實作 `scan()` / `validate_config()` / `get_default_config()`
5. 可選：實作 `evaluate()` / `on_candidate_confirmed()`

 **引擎會自動載入** ，無需修改主程式。

### 9.7.4 熱重載流程

```text
1. Telegram 執行 /set_strategy {id} {param} {value}
2. ccurr-telegram 寫入 MariaDB runtime_config
3. ccurr-telegram PUBLISH config:changed
   {"scope": "strategy", "strategy_id": "volume_breakout_pullback_v1"}
4. ccurr-strategy 的 ConfigWatcher 收到訊息
5. 呼叫 engine.reload_strategy(strategy_id)
6. 停止舊實例 → 重新載入類別 → 讀新配置 → 建立新實例
7. 毫秒級生效
```

---

## 9.8 關鍵設計決策

### 9.8.1 為什麼 Step 不強制繼承 `BaseStep`

| 方案               | 優點     | 缺點     |
| ------------------ | -------- | -------- |
| **強制繼承** | 統一介面 | 限制彈性 |
| **不強制**   | 彈性大   | 需靠約定 |

 **選擇** ：提供 `BaseStep` 但 **不強制繼承** 。子類只需遵守介面約定。

### 9.8.2 為什麼 `Candidate` 用混合模型

| 方案           | 優點     | 缺點       |
| -------------- | -------- | ---------- |
| 全部 Pydantic  | 型別安全 | 難擴展     |
| 全部 dict      | 彈性     | 不安全     |
| **混合** | 兩者兼顧 | 需明確分層 |

 **選擇** ：基礎欄位 Pydantic，策略專屬資料用 `data: dict`。

 **理由** ：

* 基礎欄位（`symbol`、`trace_id`、`current_price`）用 Pydantic 鎖死
  → Telegram / Executor 不會因缺欄位 Crash
* 策略專屬資料（例如未來「均線交叉策略」的 `ma50_value`）用 `data: dict`
  → 不需改底層 Schema

### 9.8.3 為什麼 `StrategyContext` 要集中管理

| 原因               | 說明                              |
| ------------------ | --------------------------------- |
| **統一介面** | 策略不需直接碰 ClickHouse / Redis |
| **可測試**   | 可 mock Context 進行單元測試      |
| **配置快取** | 避免每個 Step 都讀 MariaDB        |
| **降級處理** | Context 可統一處理降級邏輯        |
| **時間抽象** | 回測時可覆寫`now_ms()`          |

### 9.8.4 為什麼 `scan()` 只回傳 `Candidate`

| 原因               | 說明                                |
| ------------------ | ----------------------------------- |
| **人工確認** | SEMI 模式需等待                     |
| **模式分流** | AUTO / SEMI / MANUAL 在 Step 7 處理 |
| **追蹤**     | Candidate 有獨立生命週期            |
| **審計**     | 記錄候選產生到確認的過程            |

---

## 9.9 UDS API（與插件互動）

| Method | Path                        | 說明             |
| ------ | --------------------------- | ---------------- |
| GET    | `/strategy/list`          | 列出所有策略     |
| GET    | `/strategy/{id}`          | 查策略詳情       |
| GET    | `/strategy/{id}/config`   | 查策略配置       |
| PUT    | `/strategy/{id}/config`   | 改策略配置       |
| POST   | `/strategy/{id}/enable`   | 啟用策略         |
| POST   | `/strategy/{id}/disable`  | 停用策略         |
| POST   | `/strategy/reload`        | 重新載入所有策略 |
| GET    | `/candidates`             | 查詢候選清單     |
| GET    | `/candidate/{trace_id}`   | 查單一候選       |
| POST   | `/candidate/confirm`      | 使用者確認候選   |
| POST   | `/candidate/reject`       | 使用者拒絕候選   |
| POST   | `/candidate/manual_enter` | 手動進場         |

### `POST /candidate/confirm` 規格

 **Request body** ：

```json
{
    "trace_id": "uuid-v4",
    "action": "CONFIRM",
    "custom_tp": 75000.0
}
```

 **處理** ：

1. 檢查 ZSET → `trace_id` 還在 pending
2. 從 `strategy:candidate_data` 讀取 Candidate
3. 設定 `status=CONFIRMED`、`review_action=CONFIRM`
4. 呼叫 `engine.execute_step8_pricing(candidate, custom_tp)`
5. 清理 ZSET + Hash
6. 回傳 `{ok: true}`

---

## 第 9 章完成 ✅

 **已完成** ：

* 9.0 整體架構
* 9.1 `BaseStrategy` 抽象類
* 9.2 `BaseStep` 抽象類（可選）
* 9.3 `StrategyContext` 介面
* 9.4 資料模型
* 9.5 各 Step 類別介面規格
* 9.6 插件註冊與載入
* 9.7 完整策略實作範例
* 9.8 關鍵設計決策
* 9.9 UDS API

# 第 10 章：回測接口

> 本章定義如何用歷史資料測試策略，包含架構、虛擬時鐘、MockBroker、績效分析。

---

## 10.0 回測的定位

### 10.0.1 為什麼需要回測

| 目的                 | 說明                             |
| -------------------- | -------------------------------- |
| **驗證策略**   | 在投入實盤前，確認策略有正期望值 |
| **參數調優**   | 找出最佳參數組合                 |
| **風險評估**   | 了解最大回撤、夏普比率           |
| **避免過擬合** | 用測試集驗證訓練集結果           |
| **心理準備**   | 知道策略在極端行情下的表現       |

### 10.0.2 核心設計原則

| 原則                     | 說明                           |
| ------------------------ | ------------------------------ |
| **策略代碼零修改** | 同一個策略類別，回測與實盤共用 |
| **時間抽象**       | 用虛擬時鐘取代真實時間         |
| **資料抽象**       | 用歷史資料取代 ClickHouse 直連 |
| **訂單抽象**       | 用 MockBroker 取代幣安 API     |
| **強制 AUTO 模式** | 回測無法模擬人工確認           |
| **可重現**         | 相同輸入 → 相同輸出           |

### 10.0.3 與實盤的關鍵差異

| 項目      | 實盤            | 回測           |
| --------- | --------------- | -------------- |
| 時間      | 真實時間        | 虛擬時鐘       |
| K 線來源  | ClickHouse 直連 | 預載入記憶體   |
| 訂單執行  | 幣安 API        | MockBroker     |
| WebSocket | 實時數據        | 禁用           |
| 人工確認  | SEMI / MANUAL   | 強制 AUTO      |
| 超時機制  | Redis ZSET      | 記憶體虛擬佇列 |
| 外部事件  | 突發新聞        | 假設不存在     |

---

## 10.1 整體架構

### 10.1.1 獨立容器 `ccurr-backtest`

```text
┌─────────────────────────────────────────────────────────────┐
│                   ccurr-backtest                            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              BacktestEngine                           │ │
│  │                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │VirtualClock  │  │DataProvider  │  │MockBroker  │  │ │
│  │  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │ │
│  │         │                  │                 │         │ │
│  │         ▼                  ▼                 ▼         │ │
│  │  ┌──────────────────────────────────────────────┐    │ │
│  │  │      BacktestContext（繼承 StrategyContext） │    │ │
│  │  └──────────────────────────────────────────────┘    │ │
│  │                                                        │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │       策略插件（與 ccurr-strategy 共用）              │ │
│  │       VolumeBreakoutPullbackV1                        │ │
│  │       Step1~8 類別                                    │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              PerformanceAnalyzer                       │ │
│  │  夏普 / 回撤 / 勝率 / Profit Factor / 權益曲線         │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│                  回測報告（JSON / HTML / MariaDB）           │
└─────────────────────────────────────────────────────────────┘
```

### 10.1.2 為什麼獨立容器

| 原因                 | 說明                        |
| -------------------- | --------------------------- |
| **資源隔離**   | 回測可能吃大量 CPU / 記憶體 |
| **並行運行**   | 可同時跑多組參數            |
| **不干擾實盤** | 不會影響`ccurr-strategy`  |
| **獨立部署**   | 可在不同機器上跑            |

### 10.1.3 與 ccurr-strategy 的關係

```text
共享：

- shared/（Trace / Locks / EventBus / Config）
- plugins/（策略插件，透過 volume mount 或獨立 package）

不共享：

- 執行引擎（BacktestEngine vs StrategyEngine）
- Context（BacktestContext vs StrategyContext）
- Broker（MockBroker vs ccurr-trader）
```

關鍵：策略插件是同一個檔案，透過 Docker volume 或 pip package 共享。

---

## 10.2 虛擬時鐘

### 10.2.1 設計

```python
# app/engine/virtual_clock.py

class VirtualClock:
    """回測用的虛擬時鐘"""

    def __init__(
        self,
        start_ts: int,
        end_ts: int,
        step_ms: int = 300_000,  # 預設 5 分鐘
    ):
        self._start = start_ts
        self._end = end_ts
        self._current = start_ts
        self._step = step_ms

    def now_ms(self) -> int:
        """當前虛擬時間（毫秒）"""
        return self._current

    def advance(self) -> bool:
        """推進一個步進，回傳是否還在範圍內"""
        self._current += self._step
        return self._current < self._end

    def is_finished(self) -> bool:
        """是否已結束"""
        return self._current >= self._end

    def reset(self) -> None:
        """重置到起始時間"""
        self._current = self._start

    @property
    def start_ts(self) -> int:
        return self._start

    @property
    def end_ts(self) -> int:
        return self._end

    @property
    def step_ms(self) -> int:
        return self._step
```

### 10.2.2 步進大小的選擇

| 策略類型 | 建議步進 |
| -------- | -------- |
| 日線波段 | 1 天     |
| 4h 波段  | 1 小時   |
| 1h 波段  | 15 分鐘  |
| 5m 短線  | 5 分鐘   |
| 高頻     | 1 分鐘   |

 **建議** ：預設 5 分鐘（與 `ccurr-k5m` 一致）。

### 10.2.3 時間抽象的關鍵

所有策略中的時間呼叫必須改為從 Context 取得：

```python
# ❌ 錯誤：直接用全域函式

from shared.time_utils import now_ms
ts = now_ms()

# ✅ 正確：從 Context 取得

ts = self.context.now_ms()
```

 **需要修改的地方** ：

* Step 類別中所有 `now_ms()` → `self.context.now_ms()`
* `asyncio.sleep()` → 虛擬時鐘推進
* 時間戳比較 → 用虛擬時鐘

---

## 10.3 歷史資料提供者

### 10.3.1 設計

```python
# app/engine/data_provider.py

class HistoricalDataProvider:
    """歷史資料提供者（預載入記憶體）"""

    def __init__(self, clickhouse_reader):
        self._clickhouse = clickhouse_reader
        # {symbol: {timeframe: list[Kline]}}
        self._cache: dict[str, dict[str, list]] = {}
        self._cache_index: dict[str, dict[str, dict[int, int]]] = {}
        # 索引：{symbol: {timeframe: {ts: index}}}

    async def preload(
        self,
        symbols: list[str],
        timeframes: list[str],
        start_ts: int,
        end_ts: int,
    ) -> None:
        """預載入所有 K 線到記憶體"""
        log.info("preload_started",
                 symbols=len(symbols),
                 timeframes=timeframes)

        for symbol in symbols:
            self._cache[symbol] = {}
            self._cache_index[symbol] = {}

            for tf in timeframes:
                # 從 ClickHouse 讀
                klines = await self._clickhouse.get_klines_range(
                    symbol, tf, start_ts, end_ts,
                )

                self._cache[symbol][tf] = klines

                # 建立索引
                self._cache_index[symbol][tf] = {
                    k.timestamp: i for i, k in enumerate(klines)
                }

        log.info("preload_done")

    def get_klines_at(
        self,
        symbol: str,
        timeframe: str,
        ts: int,
        limit: int,
    ) -> list:
        """取得 ts 時刻之前的 N 根 K 線"""
        if symbol not in self._cache:
            return []
        if timeframe not in self._cache[symbol]:
            return []

        klines = self._cache[symbol][timeframe]
        index = self._cache_index[symbol][timeframe]

        # 找出 ts 對應的索引
        if ts not in index:
            # ts 不是 K 線的開盤時間，找最接近的
            candidates = [t for t in index.keys() if t <= ts]
            if not candidates:
                return []
            ts = max(candidates)

        end_idx = index[ts] + 1
        start_idx = max(0, end_idx - limit)

        return klines[start_idx:end_idx]

    def get_kline_at(
        self,
        symbol: str,
        timeframe: str,
        ts: int,
    ) -> object | None:
        """取得 ts 時刻的 K 線"""
        klines = self.get_klines_at(symbol, timeframe, ts, 1)
        return klines[0] if klines else None

    def get_range(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
    ) -> list:
        """取得時間範圍內的 K 線"""
        if symbol not in self._cache:
            return []
        klines = self._cache[symbol][timeframe]
        return [k for k in klines if start_ts <= k.timestamp <= end_ts]
```

### 10.3.2 記憶體估算

假設：

* 200 個 symbol
* 1d / 4h / 1h 三個 timeframe
* 1 年歷史

| Timeframe      | 每 symbol 根數 | 200 symbol 總根數   | 記憶體估算        |
| -------------- | -------------- | ------------------- | ----------------- |
| 1d             | 365            | 73,000              | ~10 MB            |
| 4h             | 2,190          | 438,000             | ~60 MB            |
| 1h             | 8,760          | 1,752,000           | ~240 MB           |
| **合計** |                | **2,263,000** | **~310 MB** |

 **結論** ：預載入記憶體完全可行。

### 10.3.3 若資料量過大

若未來擴展到 5m 或更多 symbol：

| 方案                      | 說明            |
| ------------------------- | --------------- |
| **LRU 快取**        | 只保留最近 N 根 |
| **分批載入**        | 按時間段載入    |
| **磁碟快取**        | 用 Parquet 檔案 |
| **ClickHouse 直查** | 每次現查（慢）  |

 **第一版** ：全部預載入記憶體。

---

## 10.4 MockBroker

> **非規範回測示例（illustrative / non-normative）**：本節程式碼只示範 Chapter 9 canonical broker/provider contract 的一種本機回測實作。`_pending_ocos` 是此示例的 private implementation state，不是 engine、strategy 或其他 adapter 可依賴的 public API；正式實作必須透過 Chapter 9 定義的 public broker protocol/adapter methods 存取 pending OCO 狀態。

### 10.4.1 設計

```python
# app/engine/mock_broker.py

class MockBroker:
    """模擬交易所"""

    def __init__(
        self,
        fee_pct: Decimal = Decimal("0.1"),       # 手續費 0.1%，百分比點
        slippage_pct: Decimal = Decimal("0.05"), # 滑價 0.05%，百分比點
        initial_balance: Decimal = Decimal("10000"),
    ):
        self._fee_pct = Decimal(str(fee_pct)) / Decimal("100")
        self._slippage_pct = Decimal(str(slippage_pct)) / Decimal("100")
        self._initial_balance = initial_balance
        self._balance = initial_balance
        self._positions: dict[str, Position] = {}
        self._pending_orders: dict[str, list[OrderRequest]] = {}
        self._trades: list[Trade] = []
        self._equity_curve: list[EquityPoint] = []
        self._pending_ocos: dict[str, dict] = {}

    def register_pending_oco(
        self,
        client_order_id: str,
        plan: dict,
    ) -> None:
        """Register an OCO plan through the public backtest broker boundary."""
        self._pending_ocos[client_order_id] = plan

    def has_pending_oco(self, client_order_id: str) -> bool:
        """Return whether an entry order has a pending OCO plan."""
        return client_order_id in self._pending_ocos

    def pop_pending_oco(self, client_order_id: str) -> dict | None:
        """Consume and return an OCO plan after the entry fill."""
        return self._pending_ocos.pop(client_order_id, None)

    async def place_order(
        self,
        order: OrderRequest,
        current_price: Decimal,
        current_kline: object,
    ) -> OrderResponse:
        """模擬下單

        依訂單類型處理：
        - MARKET：以 current_price ± 滑價成交
        - LIMIT：加入掛單佇列
        """
        if order.type == "MARKET":
            return await self._execute_market(order, current_price)
        elif order.type == "LIMIT":
            return await self._place_limit(order)
        else:
            return OrderResponse(
                ok=False,
                status="REJECTED",
                error={"code": "UNSUPPORTED_TYPE"},
            )

    async def _execute_market(
        self,
        order: OrderRequest,
        current_price: Decimal,
    ) -> OrderResponse:
        """市價單立即成交"""
        # 滑價處理
        if order.side == "BUY":
            fill_price = current_price * (1 + self._slippage_pct)
        else:
            fill_price = current_price * (1 - self._slippage_pct)

        # 計算手續費
        fee = fill_price * order.quantity * self._fee_pct

        # 更新餘額與持倉
        await self._apply_fill(order, fill_price, order.quantity, fee)

        return OrderResponse(
            ok=True,
            orderId=self._next_order_id(),
            clientOrderId=order.clientOrderId,
            status="FILLED",
            executedQty=order.quantity,
            avgPrice=fill_price,
        )

    async def _place_limit(self, order: OrderRequest) -> OrderResponse:
        """限價單加入掛單佇列"""
        self._pending_orders.setdefault(order.symbol, []).append(order)

        return OrderResponse(
            ok=True,
            orderId=self._next_order_id(),
            clientOrderId=order.clientOrderId,
            status="NEW",
        )

    async def check_pending_orders(
        self,
        symbol: str,
        current_kline: object,
    ) -> list[dict]:
        """檢查掛單是否成交

        用當前 K 線的高低價判斷：
        - LIMIT BUY：若 kline.low <= order.price → 成交
        - LIMIT SELL：若 kline.high >= order.price → 成交
        """
        fills = []
        pending = self._pending_orders.get(symbol, [])
        remaining = []

        for order in pending:
            filled = False

            if order.side == "BUY" and current_kline.low <= order.price:
                fill_price = order.price
                filled = True
            elif order.side == "SELL" and current_kline.high >= order.price:
                fill_price = order.price
                filled = True

            if filled:
                fee = fill_price * order.quantity * self._fee_pct
                await self._apply_fill(order, fill_price, order.quantity, fee)

                fills.append({
                    "order": order,
                    "fill_price": fill_price,
                    "qty": order.quantity,
                    "fee": fee,
                    "ts": current_kline.timestamp,
                })
            else:
                remaining.append(order)

        self._pending_orders[symbol] = remaining
        return fills

    async def cancel_order(
        self,
        symbol: str,
        client_order_id: str,
    ) -> dict:
        """取消掛單"""
        pending = self._pending_orders.get(symbol, [])
        self._pending_orders[symbol] = [
            o for o in pending if o.clientOrderId != client_order_id
        ]
        return {"ok": True}

    async def check_oco_orders(
        self,
        symbol: str,
        current_kline: object,
    ) -> list[dict]:
        """檢查 OCO（停損停利）是否觸發"""
        # 類似 check_pending_orders，但處理 STOP_LOSS_LIMIT
        ...

    async def _apply_fill(
        self,
        order: OrderRequest,
        fill_price: Decimal,
        qty: Decimal,
        fee: Decimal,
    ) -> None:
        """應用到餘額與持倉"""
        if order.side == "BUY":
            cost = fill_price * qty + fee
            self._balance -= cost

            if order.symbol not in self._positions:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=Decimal(0),
                    entry_price=Decimal(0),
                )

            pos = self._positions[order.symbol]
            new_qty = pos.quantity + qty
            if pos.quantity > 0:
                new_entry = (
                    pos.quantity * pos.entry_price + qty * fill_price
                ) / new_qty
            else:
                new_entry = fill_price

            pos.quantity = new_qty
            pos.entry_price = new_entry

        elif order.side == "SELL":
            proceeds = fill_price * qty - fee
            self._balance += proceeds

            pos = self._positions.get(order.symbol)
            if pos:
                pnl = (fill_price - pos.entry_price) * qty
                pos.quantity -= qty

                self._trades.append(Trade(
                    symbol=order.symbol,
                    entry_price=pos.entry_price,
                    exit_price=fill_price,
                    quantity=qty,
                    pnl=pnl,
                    fee=fee,
                    ts=0,
                ))

                if pos.quantity <= 0:
                    del self._positions[order.symbol]

    def get_balance(self) -> Decimal:
        return self._balance

    def get_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def get_trades(self) -> list[Trade]:
        return list(self._trades)

    def get_equity(self, prices: dict[str, Decimal]) -> Decimal:
        """計算總權益"""
        equity = self._balance
        for symbol, pos in self._positions.items():
            if symbol in prices:
                equity += pos.quantity * prices[symbol]
        return equity

    def _next_order_id(self) -> int:
        """產生下一個訂單 ID"""
        ...
```

### 10.4.2 成交判斷的精確度

 **問題** ：用 K 線的 `low` / `high` 判斷是否成交，可能高估成交率。

 **改進** ：

| 情境                                         | 處理                                      |
| -------------------------------------------- | ----------------------------------------- |
| LIMIT BUY，`low <= price`                  | 以`price`成交（保守）                   |
| LIMIT BUY，`low < price`且`open < price` | 以`open`成交（更真實）                  |
| LIMIT SELL，`high >= price`                | 以`price`成交                           |
| STOP_LOSS，`low <= stop_price`             | 以`stop_price`成交，或`open`if gapped |

 **建議** ：第一版用簡單判斷（`low <= price` → 成交），未來再加精細邏輯。

### 10.4.3 手續費與滑價

| 參數             | 預設 | 說明             |
| ---------------- | ---- | ---------------- |
| `fee_pct`      | 0.1  | 幣安現貨標準費率 |
| `slippage_pct` | 0.05 | 市價單滑價       |
| `bnb_discount` | 0.75 | BNB 折扣（可選） |

 **若使用 BNB 支付手續費** ：

```text
effective_fee_pct = fee_pct * bnb_discount
```

---

## 10.5 BacktestContext

### 10.5.1 設計

```python
# app/context/backtest_context.py

class BacktestContext(StrategyContext):
    """回測用的 Context（繼承 StrategyContext）"""

    def __init__(
        self,
        clock: VirtualClock,
        data_provider: HistoricalDataProvider,
        config: dict,
        broker: MockBroker,
        strategy_id: str,
    ):
        # 不呼叫 super().__init__()，因為不需要真實的 ClickHouse / Redis
        self._clock = clock
        self._data = data_provider
        self._config = config
        self._broker = broker
        self._strategy_id = strategy_id
        self._config_cache = dict(config)

    # === 時間（覆寫）===

    def now_ms(self) -> int:
        """虛擬時間"""
        return self._clock.now_ms()

    # === 資料 ===

    async def get_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_ts: int | None = None,
    ) -> list:
        ts = before_ts or self._clock.now_ms()
        return self._data.get_klines_at(symbol, timeframe, ts, limit)

    async def get_current_price(self, symbol: str) -> Decimal | None:
        """按 5m → 1h → 4h → 1d 順序讀取"""
        for tf in ["5m", "1h", "4h", "1d"]:
            klines = self._data.get_klines_at(
                symbol, tf, self._clock.now_ms(), 1,
            )
            if klines:
                return klines[0].close
        return None

    # === 持倉 ===

    async def get_position(self, symbol: str) -> dict | None:
        """從 MockBroker 讀取持倉"""
        pos = self._broker.get_positions().get(symbol)
        if not pos or pos.quantity <= 0:
            return None
        return {
            "symbol": pos.symbol,
            "quantity": str(pos.quantity),
            "entry_price": str(pos.entry_price),
        }

    async def get_all_positions(self) -> dict[str, dict]:
        positions = {}
        for symbol, pos in self._broker.get_positions().items():
            positions[symbol] = {
                "symbol": pos.symbol,
                "quantity": str(pos.quantity),
                "entry_price": str(pos.entry_price),
            }
        return positions

    # === 配置 ===

    async def get_config(self, key: str, default=None):
        return self._config_cache.get(key, default)
```

### 10.5.2 時間抽象的關鍵修改

#### 策略與 Step 類別中的所有時間呼叫必須改為：

```python
# ❌ 錯誤

ts = now_ms()

# ✅ 正確

ts = self.context.now_ms()
```

 **需要修改的檔案** ：

* `plugins/steps/step*.py`：所有 `now_ms()` 呼叫
* `plugins/base_step.py`：提供 `self.context.now_ms()`
* `plugins/base_strategy.py`：提供 `self.context.now_ms()`

---

## 10.6 BacktestEngine

### 10.6.1 主引擎

```python
# app/engine/backtest_engine.py

class BacktestEngine:
    """回測引擎"""

    def __init__(
        self,
        settings: BacktestSettings,
        data_provider: HistoricalDataProvider,
        broker: MockBroker,
        plugin_loader: PluginLoader,
    ):
        self._settings = settings
        self._data = data_provider
        self._broker = broker
        self._loader = plugin_loader
        self._strategies: dict[str, BaseStrategy] = {}

    async def run(
        self,
        strategy_id: str,
        config: dict,
        start_ts: int,
        end_ts: int,
        symbols: list[str],
        timeframes: list[str] = ["1d", "4h", "1h"],
        step_ms: int = 300_000,
    ) -> BacktestResult:
        """執行回測"""
        log.info("backtest_started",
                 strategy_id=strategy_id,
                 start_ts=start_ts,
                 end_ts=end_ts,
                 symbols=len(symbols))

        # 1. 載入策略
        strategy_cls = self._loader._loaded.get(strategy_id)
        if not strategy_cls:
            raise ValueError(f"Strategy not found: {strategy_id}")

        # 2. 建立虛擬時鐘
        clock = VirtualClock(start_ts, end_ts, step_ms)

        # 3. 預載入資料
        await self._data.preload(symbols, timeframes, start_ts, end_ts)

        # 4. 建立 BacktestContextBuilder（實作 Chapter 9 canonical ContextBuilder）
        context_builder = BacktestContextBuilder(
            clock=clock,
            data_provider=self._data,
            config=config,
            broker=self._broker,
            strategy_id=strategy_id,
        )

        # 5. 建立策略實例；live/backtest 都使用 (config, context_builder)
        strategy = strategy_cls(config, context_builder)
        context = await context_builder.build(strategy_id)
        await strategy.on_start(context)

        # 6. 主迴圈
        scan_interval_ms = config.get("scan_interval_sec", 900) * 1000
        last_scan_ts = 0

        while not clock.is_finished():
            current_ts = clock.now_ms()

            # 檢查掛單成交
            await self._check_pending_orders(current_ts, symbols)

            # 檢查 OCO 觸發
            await self._check_oco_orders(current_ts, symbols)

            # 定時掃描
            if current_ts - last_scan_ts >= scan_interval_ms:
                try:
                    candidates = await asyncio.wait_for(
                        strategy.scan(),
                        timeout=60.0,
                    )

                    for candidate in candidates:
                        # 回測強制 AUTO 模式
                        await self._process_candidate(
                            strategy, candidate, current_ts,
                        )

                    last_scan_ts = current_ts
                except asyncio.TimeoutError:
                    log.warning("scan_timeout", ts=current_ts)
                except Exception as e:
                    log.error("scan_failed", error=str(e))

            # 記錄權益曲線
            await self._record_equity(current_ts, symbols)

            # 推進時鐘
            clock.advance()

        await strategy.on_stop()

        # 8. 產生報告
        result = self._build_result(strategy_id, clock)

        log.info("backtest_done",
                 total_return_pct=result.total_return_pct,
                 trade_count=result.trade_count)

        return result

    async def _process_candidate(
        self,
        strategy: BaseStrategy,
        candidate: Candidate,
        current_ts: int,
    ) -> None:
        """處理候選（回測強制 AUTO 模式）"""
        signal = await strategy.evaluate(candidate)
        if not signal:
            return

        # 送到 MockBroker
        entry_order = OrderRequest(
            clientOrderId=f"{signal.signalId}-entry",
            symbol=signal.symbol,
            side="BUY",
            type=signal.plan["entry"]["type"],
            quantity=self._calc_qty(signal, current_ts),
            price=signal.plan["entry"].get("price"),
        )

        current_price = await self._data.get_current_price_async(
            signal.symbol, current_ts,
        )
        current_kline = self._data.get_kline_at(
            signal.symbol, "1m", current_ts,
        )

        await self._broker.place_order(
            entry_order, current_price, current_kline,
        )

        # 記錄 OCO 參數
        self._broker.register_pending_oco(
            entry_order.clientOrderId,
            signal.plan,
        )

    async def _check_pending_orders(
        self,
        current_ts: int,
        symbols: list[str],
    ) -> None:
        """檢查掛單成交"""
        for symbol in symbols:
            kline = self._data.get_kline_at(symbol, "1m", current_ts)
            if not kline:
                continue

            fills = await self._broker.check_pending_orders(symbol, kline)

            # 成交後，建立 OCO
            for fill in fills:
                order = fill["order"]
                if self._broker.has_pending_oco(order.clientOrderId):
                    await self._place_oco(order, fill, current_ts)

    async def _place_oco(
        self,
        entry_order: OrderRequest,
        fill: dict,
        current_ts: int,
    ) -> None:
        """建立 OCO（停損停利）"""
        plan = self._broker.pop_pending_oco(entry_order.clientOrderId)
        if not plan:
            return

        # 建立停利單
        tp_order = OrderRequest(
            clientOrderId=f"{entry_order.clientOrderId}-tp",
            symbol=entry_order.symbol,
            side="SELL",
            type="LIMIT",
            quantity=fill["qty"],
            price=plan["take_profit"]["price"],
        )
        await self._broker._place_limit(tp_order)

        # 建立停損單
        sl_order = OrderRequest(
            clientOrderId=f"{entry_order.clientOrderId}-sl",
            symbol=entry_order.symbol,
            side="SELL",
            type="STOP_LOSS_LIMIT",
            quantity=fill["qty"],
            stopPrice=plan["stop_loss"]["stop_price"],
            price=plan["stop_loss"]["stop_limit_price"],
        )
        await self._broker._place_limit(sl_order)

    async def _check_oco_orders(
        self,
        current_ts: int,
        symbols: list[str],
    ) -> None:
        """檢查 OCO 觸發"""
        # 類似 check_pending_orders，但處理 STOP_LOSS_LIMIT
        ...

    async def _record_equity(
        self,
        current_ts: int,
        symbols: list[str],
    ) -> None:
        """記錄權益曲線"""
        prices = {}
        for symbol in symbols:
            price = await self._data.get_current_price_async(
                symbol, current_ts,
            )
            if price:
                prices[symbol] = price

        equity = self._broker.get_equity(prices)
        self._broker._equity_curve.append(EquityPoint(
            ts=current_ts,
            equity=equity,
        ))

    def _build_result(
        self,
        strategy_id: str,
        clock: VirtualClock,
    ) -> BacktestResult:
        """產生回測結果"""
        analyzer = PerformanceAnalyzer(
            initial_balance=self._broker._initial_balance,
            final_balance=self._broker.get_balance(),
            trades=self._broker.get_trades(),
            equity_curve=self._broker._equity_curve,
        )
        return analyzer.analyze(strategy_id, clock)
```

### 10.6.2 回測執行流程

```text
1. 載入策略
2. 建立虛擬時鐘（start_ts → end_ts，步進 step_ms）
3. 預載入歷史資料
4. 建立 BacktestContext
5. 建立策略實例
6. 主迴圈：
   while not clock.is_finished():
   a. 檢查掛單成交（用當前 K 線的高低價）
   b. 檢查 OCO 觸發
   c. 定時掃描（每 scan_interval_sec）
   - 呼叫 strategy.scan()
   - 處理候選 → 送 MockBroker
   d. 記錄權益曲線
   e. 時鐘推進
7. 清理
8. 產生報告
```

---

## 10.7 績效分析

### 10.7.1 分析器

```python
# app/analyzers/performance.py

class PerformanceAnalyzer:
    """績效分析"""

    def __init__(
        self,
        initial_balance: Decimal,
        final_balance: Decimal,
        trades: list[Trade],
        equity_curve: list[EquityPoint],
    ):
        self._initial = initial_balance
        self._final = final_balance
        self._trades = trades
        self._equity = equity_curve

    def analyze(
        self,
        strategy_id: str,
        clock: VirtualClock,
    ) -> BacktestResult:
        """產生完整回測結果"""
        # 基礎統計
        total_return_pct = (
            (self._final - self._initial) / self._initial * Decimal("100")
        )

        win_trades = [t for t in self._trades if t.pnl > 0]
        loss_trades = [t for t in self._trades if t.pnl < 0]

        trade_count = len(self._trades)
        win_count = len(win_trades)
        loss_count = len(loss_trades)
        win_rate = (
            Decimal(win_count) / Decimal(trade_count)
            if trade_count > 0 else Decimal("0")
        )

        total_win = sum(t.pnl for t in win_trades)
        total_loss = abs(sum(t.pnl for t in loss_trades))
        profit_factor = total_win / total_loss if total_loss > 0 else Decimal("0")

        # 夏普比率
        sharpe = self._calc_sharpe()

        # 最大回撤
        max_dd = self._calc_max_drawdown()

        # 平均持倉時間
        avg_holding_hours = self._calc_avg_holding_hours()

        return BacktestResult(
            strategy_id=strategy_id,
            start_ts=clock.start_ts,
            end_ts=clock.end_ts,
            initial_balance=self._initial,
            final_balance=self._final,
            total_return_pct=total_return_pct,
            trade_count=trade_count,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            avg_holding_hours=avg_holding_hours,
            trades=self._trades,
            equity_curve=self._equity,
        )

    def _calc_sharpe(self) -> Decimal:
        """計算夏普比率（年化）"""
        if len(self._equity) < 2:
            return Decimal("0")

        returns: list[Decimal] = []
        for i in range(1, len(self._equity)):
            prev = self._equity[i-1].equity
            curr = self._equity[i].equity
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return Decimal("0")

        import statistics
        mean_return = Decimal(str(statistics.mean(returns)))
        std_return = Decimal(str(statistics.stdev(returns))) if len(returns) > 1 else Decimal("0")

        if std_return == 0:
            return Decimal("0")

        # 年化（假設每步 5 分鐘）
        periods_per_year = 365 * 24 * 12
        return (mean_return / std_return) * Decimal(str(periods_per_year ** 0.5))

    def _calc_max_drawdown(self) -> Decimal:
        """計算最大回撤（百分比點）"""
        if not self._equity:
            return Decimal("0")

        peak = self._equity[0].equity
        max_dd = Decimal("0")

        for point in self._equity:
            if point.equity > peak:
                peak = point.equity

            if peak > 0:
                dd = (peak - point.equity) / peak
                if dd > max_dd:
                    max_dd = dd

        return max_dd * Decimal("100")

    def _calc_avg_holding_hours(self) -> Decimal:
        """計算平均持倉時間"""
        if not self._trades:
            return Decimal("0")

        total_hours = sum(
            (Decimal(t.exit_ts) - Decimal(t.entry_ts)) / Decimal("3600000")
            for t in self._trades
            if hasattr(t, "entry_ts") and hasattr(t, "exit_ts")
        )
        return total_hours / Decimal(len(self._trades))
```

### 10.7.2 回測結果模型

```python
class BacktestResult(BaseModel):
    """回測結果"""

    strategy_id: str
    start_ts: int
    end_ts: int
    initial_balance: Decimal
    final_balance: Decimal
    total_return_pct: Decimal

    # 交易統計
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: Decimal
    profit_factor: Decimal

    # 風險指標
    sharpe_ratio: Decimal
    max_drawdown_pct: Decimal
    avg_holding_hours: Decimal

    # 詳細資料
    trades: list[Trade]
    equity_curve: list[EquityPoint]

    # 可選
    config: dict | None = None
```

### 10.7.3 輸出格式

#### JSON

```json
{
    "strategy_id": "volume_breakout_pullback_v1",
    "start_ts": 1726000000000,
    "end_ts": 1728600000000,
    "initial_balance": "10000.00",
    "final_balance": "12500.00",
    "total_return_pct": 25.0,
    "trade_count": 42,
    "win_count": 25,
    "loss_count": 17,
    "win_rate": 0.595,
    "profit_factor": 2.1,
    "sharpe_ratio": 1.8,
    "max_drawdown_pct": 12.5,
    "avg_holding_hours": 36.5
}
```

#### HTML 報告

產生含以下內容的 HTML：

* 績效摘要
* 權益曲線圖
* 回撤圖
* 交易列表
* 月度績效

#### MariaDB

`backtest_results` 的唯一 CREATE TABLE 定義見 [PART02 Chapter 3 §3.2.13](BLUEPRINT-PART02-Chapter03-04-DataLayer.md)。Chapter 10 只描述寫入 adapter 與回測結果欄位，不得複製或修改 DDL。

---

## 10.8 參數掃描

### 10.8.1 設計

```python
class ParameterSweep:
    """參數掃描"""

    def __init__(self, engine: BacktestEngine):
        self._engine = engine

    async def sweep(
        self,
        strategy_id: str,
        base_config: dict,
        param_grid: dict[str, list],
        start_ts: int,
        end_ts: int,
        symbols: list[str],
    ) -> list[BacktestResult]:
        """對所有參數組合進行回測

        Args:
            param_grid: {
                "threshold_ma7": [2.5, 3.0, 3.5],
                "phase1_min_rise_pct": [10, 15, 20],
            }
        """
        # 產生所有組合
        import itertools
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        log.info("sweep_started",
                 total_combinations=len(combinations))

        results = []
        for i, combo in enumerate(combinations):
            config = dict(base_config)
            for key, value in zip(keys, combo):
                config[key] = value

            log.info("sweep_running",
                     combo_idx=i+1,
                     total=len(combinations),
                     config=combo)

            try:
                result = await self._engine.run(
                    strategy_id=strategy_id,
                    config=config,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    symbols=symbols,
                )
                result.config = config
                results.append(result)
            except Exception as e:
                log.error("sweep_run_failed",
                         combo_idx=i+1,
                         error=str(e))

        # 按總報酬排序
        results.sort(key=lambda r: r.total_return_pct, reverse=True)

        log.info("sweep_done", total=len(results))
        return results
```

### 10.8.2 輸出

```text
參數掃描結果（按總報酬排序）

| 排名 | threshold_ma7 | min_rise_pct | 總報酬 | 夏普 | 最大回撤 | 交易數 |
|------|--------------|-------------|--------|------|---------|--------|
| 1    | 2.5          | 15          | +42.3% | 2.1  | -8.5%   | 38     |
| 2    | 3.0          | 15          | +38.7% | 1.9  | -10.2%  | 42     |
| 3    | 2.5          | 10          | +35.1% | 1.7  | -12.8%  | 55     |
| ...  | ...          | ...         | ...    | ...  | ...     | ...    |
```

### 10.8.3 過擬合警告

 **問題** ：參數掃描容易過擬合。

 **解決** ：

1. **訓練集 + 測試集分割** ：用前 70% 時間優化，後 30% 驗證
2. **交叉驗證** ：多個時間段驗證
3. **參數穩定區間** ：找「高原」而非「尖峰」
4. **樣本外測試** ：用未見過的資料驗證

---

## 10.9 與實盤的差異處理

### 10.9.1 WebSocket 資料

 **問題** ：策略可能依賴 OBI、大單流向等實時數據。

 **處理** ：

| 選項               | 說明                       |
| ------------------ | -------------------------- |
| **禁用**     | 回測時跳過相關檢查         |
| **歷史快照** | 從 ClickHouse 讀取歷史 OBI |
| **模擬**     | 用 K 線資料近似            |

 **建議** ：第一版禁用，Step 中加 `if self.context.is_backtest: skip` 判斷。

### 10.9.2 人工確認

 **問題** ：SEMI / MANUAL 模式需等待使用者。

 **處理** ： **回測強制 AUTO 模式** 。

```python
if self.context.is_backtest:
    # 直接進場，不等待
    signal = await strategy.evaluate(candidate)
    await self._execute_signal(signal)
```

### 10.9.3 超時機制

 **問題** ：Redis ZSET 在回測中不可用。

 **處理** ：用 **記憶體虛擬優先佇列** 。

```python
class VirtualTimeoutQueue:
    """回測用的虛擬超時佇列"""

    def __init__(self):
        self._queue: list[tuple[int, str]] = []  # [(expire_at_ms, id)]

    def add(self, item_id: str, expire_at_ms: int) -> None:
        self._queue.append((expire_at_ms, item_id))
        self._queue.sort()

    def get_expired(self, current_ts: int) -> list[str]:
        expired = []
        remaining = []
        for expire_at, item_id in self._queue:
            if expire_at <= current_ts:
                expired.append(item_id)
            else:
                remaining.append((expire_at, item_id))
        self._queue = remaining
        return expired
```

### 10.9.4 API 呼叫

 **問題** ：回測不能呼叫幣安 API。

 **處理** ： **MockBroker 取代** 。

### 10.9.5 外部事件

 **問題** ：突發新聞、系統維護等無法模擬。

 **處理** ： **假設不存在** 。

---

## 10.10 完整目錄結構

```text
ccurr-backtest/
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
    │   ├── backtest_engine.py
    │   ├── virtual_clock.py
    │   ├── data_provider.py
    │   ├── mock_broker.py
    │   └── virtual_timeout_queue.py
    │
    ├── context/
    │   ├── __init__.py
    │   └── backtest_context.py
    │
    ├── analyzers/
    │   ├── __init__.py
    │   ├── performance.py
    │   ├── sharpe.py
    │   ├── drawdown.py
    │   └── reporter.py
    │
    ├── sweep/
    │   ├── __init__.py
    │   └── parameter_sweep.py
    │
    ├── storage/
    │   ├── __init__.py
    │   └── result_writer.py
    │
    └── http_api.py
```

---

## 10.11 CLI 與 API

### 10.11.1 CLI 指令

```bash

# 基本回測

python -m app.main backtest \
    --strategy volume_breakout_pullback_v1 \
    --start 2025-01-01 \
    --end 2025-06-30 \
    --symbols BTCUSDT,ETHUSDT,SOLUSDT \
    --balance 10000

# 參數掃描

python -m app.main sweep \
    --strategy volume_breakout_pullback_v1 \
    --param threshold_ma7=2.5,3.0,3.5 \
    --param phase1_min_rise_pct=10,15,20 \
    --start 2025-01-01 \
    --end 2025-06-30 \
    --symbols BTCUSDT,ETHUSDT
```

### 10.11.2 HTTP API

| Method | Path                          | 說明         |
| ------ | ----------------------------- | ------------ |
| POST   | `/backtest/run`             | 執行回測     |
| POST   | `/backtest/sweep`           | 參數掃描     |
| GET    | `/backtest/results`         | 查詢歷史結果 |
| GET    | `/backtest/result/{run_id}` | 查單一結果   |
| GET    | `/health`                   | 健康檢查     |

### 10.11.3 回測請求範例

`POST /backtest/run`

```json
{
    "strategy_id": "volume_breakout_pullback_v1",
    ...
}
```

## 10.12 環境變數

| 變數                     | 說明               | 預設                       |
| ------------------------ | ------------------ | -------------------------- |
| `SERVICE_NAME`         | `ccurr-backtest` | —                         |
| `UDS_PATH`             | UDS 路徑           | `/sockets/backtest.sock` |
| `PLUGINS_DIR`          | 插件目錄           | `/app/plugins`           |
| `CLICKHOUSE_HOST`      | ClickHouse 位址    | `ccurr-clickhouse`       |
| `MARIADB_HOST`         | MariaDB 位址       | `ccurr-mariadb`          |
| `DEFAULT_FEE_PCT`      | 手續費             | `0.1`                    |
| `DEFAULT_SLIPPAGE_PCT` | 滑價               | `0.05`                   |
| `DEFAULT_STEP_MS`      | 虛擬時鐘步進       | `300000`                 |

---

### 10.14 Backtest DB exception boundary

- **Fatal at boot**：ClickHouse connection failure, empty/core timeframe data, insufficient indicator warmup, or MariaDB runtime config read failure aborts the run.
- **Non-fatal**：one parameter-sweep combination failure is isolated and logged; result output is written as JSON/HTML to `/app/results`.
- **Excluded**：BacktestContext does not connect to Redis, live locks, Pub/Sub, `ccurr-dbwriter`, or dbwriter async queues; it uses VirtualTimeoutQueue/MockBroker in memory. Results are not written to live DB tables by the backtest process. Any future DB export must be a separate, explicitly authorized offline exporter outside this contract.

---


### 10.13.1 為什麼獨立容器

| 原因                 | 說明                        |
| -------------------- | --------------------------- |
| **資源隔離**   | 回測可能吃大量 CPU / 記憶體 |
| **並行運行**   | 可同時跑多組參數            |
| **不干擾實盤** | 不影響`ccurr-strategy`    |

### 10.13.2 為什麼預載入記憶體

| 原因               | 說明                              |
| ------------------ | --------------------------------- |
| **速度**     | 記憶體讀取比 ClickHouse 快 100 倍 |
| **簡單**     | 不需處理快取失效                  |
| **資料量小** | 1 年 200 symbol 約 310 MB         |

### 10.13.3 為什麼用虛擬時鐘

| 原因             | 說明                 |
| ---------------- | -------------------- |
| **可重現** | 相同輸入 → 相同輸出 |
| **快速**   | 不需真的等 1 年      |
| **可控制** | 可暫停、跳躍、加速   |

### 10.13.4 為什麼強制 AUTO 模式

| 原因                   | 說明                       |
| ---------------------- | -------------------------- |
| **無法模擬人工** | 回測無法等待使用者點按鈕   |
| **可重現**       | 人工決策不可重現           |
| **簡化**         | 聚焦策略邏輯，不測人工流程 |

### 10.13.5 為什麼策略代碼零修改

| 原因               | 說明                           |
| ------------------ | ------------------------------ |
| **一致性**   | 回測與實盤用同一份代碼         |
| **避免偏差** | 不會「回測用這版，實盤用那版」 |
| **維護成本** | 只維護一份代碼                 |

 **實作方式** ：透過依賴注入（Context），策略不知道自己在回測還是實盤。

---

## 第 10 章完成 ✅

 **已完成** ：

* 10.0 回測的定位
* 10.1 整體架構
* 10.2 虛擬時鐘
* 10.3 歷史資料提供者
* 10.4 MockBroker
* 10.5 BacktestContext
* 10.6 BacktestEngine
* 10.7 績效分析
* 10.8 參數掃描
* 10.9 與實盤的差異處理
* 10.10 完整目錄結構
* 10.11 CLI 與 API
* 10.12 環境變數
* 10.13 關鍵設計決策

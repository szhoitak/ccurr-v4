# 第一部：系統總覽

---

## 第 0 章：系統概覽

### 0.1 目標

建立一套 **全自動加密貨幣量化交易系統** ，具備：

* 多時間級別 K 線採集與技術指標計算
* 幣安唯一出口（固定 IP，經 Tailscale → AWS VPS）
* 實時行情監控（WebSocket + OrderBook 分析）
* 多層風控（風控守門員 + 流動性檢查）
* 多階段緊急平倉機制
* 完整審計、追蹤、降級機制
* Telegram 人機介面
* 策略插件化（可熱重載、可回測）

### 0.2 硬體環境

| 項目     | 規格                                               |
| -------- | -------------------------------------------------- |
| 主機     | CM3588（32GB RAM）                                 |
| 系統     | 飛牛系統                                           |
| 容器管理 | Portainer + Docker                                 |
| 網路     | MikroTik RB5009，3 條寬頻（CMHK1 / PCCW1 / PCCW2） |
| 固定 IP  | Tailscale exit node → AWS VPS                     |
| 資料庫   | ClickHouse + MariaDB + Redis                       |

### 0.3 整體架構圖

**text**

```
┌──────────────────────────────────────────────────────────┐
│                    幣安 Binance API                       │
└────────────────────────┬─────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
      (Tailscale 固定 IP)      (macvlan 3寬頻)
              │                     │
      ┌───────▼───────┐    ┌────────▼────────────┐
      │ ccurr-trader  │    │ ccurr-k5m/k1h/k4h/k1d│
      │ (UDS: trader) │    │ (K線採集+指標)        │
      └───────┬───────┘    └────────┬────────────┘
              │                     │
              │ UDS                 │ UDS (async write)
              │                     │
      ┌───────▼─────────────────────▼────────────┐
      │              ccurr-dbwriter              │
      │           (UDS: dbwriter)                │
      │         (所有 DB 寫入統一入口)             │
      └───────┬──────────────────────────────────┘
              │
              ├──► ClickHouse
              └──► MariaDB

      ┌────────────────┐    ┌────────────────┐
      │ ccurr-strategy │───►│ Redis Pub/Sub  │
      └────────────────┘    └────────┬───────┘
              │                      │
              │                      ▼
              │              ┌──────────────┐
              │              │ccurr-executor│
              │              └──────┬───────┘
              │                     │
              │              ┌──────┴───────┐
              │              │ ccurr-risk   │
              │              │ ccurr-trader │
              │              │ccurr-dbwriter│
              │              └──────────────┘
              │
      ┌───────▼───────┐    ┌──────────────┐
      │ccurr-websocket│    │ccurr-accountsync│
      └───────────────┘    └──────────────┘

      ┌───────────────┐    ┌──────────────┐
      │ ccurr-order   │    │ccurr-override│
      └───────────────┘    └──────────────┘

      ┌───────────────┐    ┌──────────────┐
      │ccurr-telegram │    │ccurr-monitor │
      └───────────────┘    └──────────────┘

      ┌───────────────┐
      │ccurr-backtest │  ← 獨立容器，不參與實盤
      └───────────────┘
```

### 0.4 容器總覽

本系統的 Docker 容器分為三類：

| 類別 | 數量 | 說明 |
| ---- | ---- | ---- |
| **業務容器** | 16 | 參與交易邏輯（下單、風控、策略、資料採集等） |
| **基礎設施容器** | 3 | Redis / MariaDB / ClickHouse |
| **運維輔助容器** | 3 | Dozzle（日誌）+ Uptime Kuma（監控）+ Redis Insight（Redis 瀏覽） |
| **Docker 容器總數** | **22** | 以上加總 |

#### 0.4.1 業務容器（16 個）

| #  | Container         | 職責一句話                              |
| -- | ----------------- | --------------------------------------- |
| 1  | ccurr-trader      | 幣安唯一出口，代所有容器下單/查詢       |
| 2  | ccurr-dbwriter    | 所有 DB 寫入統一入口                    |
| 3  | ccurr-accountsync | 帳戶快照同步 + Symbol 同步 + BNB Keeper |
| 4  | ccurr-websocket   | 實時行情監控（WebSocket + OrderBook）   |
| 5  | ccurr-k5m         | 5 分鐘 K 線採集 + 指標                  |
| 6  | ccurr-k1h         | 1 小時 K 線採集 + 指標                  |
| 7  | ccurr-k4h         | 4 小時 K 線採集 + 指標                  |
| 8  | ccurr-k1d         | 1 日 K 線採集 + 指標                    |
| 9  | ccurr-risk        | 風控守門員（只讀 Redis）                |
| 10 | ccurr-executor    | 信號執行（含緊急通道 + 維護通道）       |
| 11 | ccurr-order       | 訂單追蹤（含寫穿 + 超時管理）           |
| 12 | ccurr-override    | 多階段緊急平倉                          |
| 13 | ccurr-strategy    | 策略引擎                                |
| 14 | ccurr-telegram    | 人機介面                                |
| 15 | ccurr-monitor     | 監控告警 + 降級維護                     |
| 16 | ccurr-backtest    | 回測引擎（獨立，不參與實盤）            |

#### 0.4.2 基礎設施容器（3 個）

| #  | Container         | 職責一句話 |
| -- | ----------------- | ---------- |
| 1  | ccurr-redis       | 熱狀態、Pub/Sub、分散式鎖、ZSET 延遲佇列 |
| 2  | ccurr-mariadb     | 冷資料（訂單、成交、審計、配置） |
| 3  | ccurr-clickhouse  | 時序資料（K 線、指標、缺口） |

#### 0.4.3 運維輔助容器（3 個）

| #  | Container              | 職責一句話 |
| -- | ---------------------- | ---------- |
| 1  | ccurr-dozzle           | 容器日誌即時查看（Web UI） |
| 2  | ccurr-uptime-kuma      | 服務健康監控（HTTP / heartbeat） |
| 3  | ccurr-redis-insight    | Redis 視覺化（Key 瀏覽、命令列） |

### 0.5 關鍵設計原則

1. **單一出口** ：只有 `ccurr-trader` 有權呼叫幣安下單/查帳戶 API
2. **資料與決策分離** ：K 線抓取、指標計算、策略決策、下單執行四條獨立管線
3. **冪等性** ：所有下單帶 `clientOrderId`
4. **狀態雙寫** ：Redis 存熱狀態，MariaDB 存冷資料，ClickHouse 存時序資料
5. **讀寫分離** ：讀 ClickHouse 直連，寫 ClickHouse 經 dbwriter
6. **故障隔離** ：任何單一容器掛掉不影響其他容器運作（降級機制）
7. **決策與風控分離** ：strategy 發意圖，risk 核算絕對值
8. **一進一出** ：每筆 `trace_id` 都是獨立的 1 Entry → 1 Exit

---

## 第 1 章：全域約定

### 1.1 技術棧

| 項目     | 約定                                                        |
| -------- | ----------------------------------------------------------- |
| 語言     | Python 3.11+                                                |
| 非同步   | 全部`asyncio`，HTTP 用`httpx.AsyncClient`               |
| 資料驗證 | Pydantic v2                                                 |
| 日誌     | `structlog`，輸出 JSON                                    |
| 設定     | `pydantic-settings`，從環境變數讀                         |
| 金額與數值 | 金額、價格、數量、成交量、比例計算一律使用`Decimal`；策略與事件模型禁止`float` | 
| 百分比單位 | 名稱含`_pct`的欄位使用「百分比點」：`Decimal("5.0")`代表 5%；公式內必須明確 `/ 100` 轉成 ratio | 
| 倍數與比例 | `ratio`/`rvol`是無單位倍數，使用`Decimal`；不得與`_pct`混用 | 
| 時間與 Clock | 策略與 Step 只能透過注入的 `StrategyContext`/`Clock` 取得時間；底層 SystemClock 才可使用 wall clock |
| 容器     | 每個 container 獨立`Dockerfile`+`requirements.txt`      |

### 1.2 統一日誌格式

**json**

```
{
  "ts": "2026-09-26T12:00:00.000Z",
  "service": "ccurr-k5m",
  "level": "INFO",
  "event": "kline_fetched",
  "trace_id": "uuid-v4",
  "symbol": "BTCUSDT",
  "timeframe": "5m",
  "count": 500,
  "duration_ms": 320
}
```

### 1.3 統一錯誤碼

| 錯誤碼                           | 意義                | 可重試 |
| -------------------------------- | ------------------- | ------ |
| `BINANCE_RATE_LIMIT`           | 幣安限流            | ✅     |
| `BINANCE_AUTH_FAILED`          | 簽名/API Key 錯誤   | ❌     |
| `BINANCE_NETWORK_ERROR`        | 網路逾時            | ✅     |
| `BINANCE_INVALID_ORDER`        | 下單參數錯誤        | ❌     |
| `BINANCE_INSUFFICIENT_BALANCE` | 餘額不足            | ❌     |
| `TRADER_UNAVAILABLE`           | trader 服務無回應   | ✅     |
| `DBWRITER_UNAVAILABLE`         | dbwriter 服務無回應 | ✅     |
| `RISK_REJECTED`                | 風控拒絕            | ❌     |
| `DB_WRITE_FAILED`              | 資料庫寫入失敗      | ✅     |
| `QUEUE_FULL`                   | 佇列已滿            | ✅     |
| `VALIDATION_ERROR`             | 參數驗證失敗        | ❌     |
| `UNKNOWN`                      | 未知錯誤            | ✅     |

### 1.4 時間對齊規則

> **Canonical representation**：domain model、API、Redis、事件 payload 與回測 Clock 一律使用 UTC epoch milliseconds `int`。`DateTime64(3)` 與 `DATETIME(3)` 僅是資料庫儲存型別，轉換由 DB adapter 負責；策略模型不得暴露 naive datetime。所有 duration 欄位必須以明確單位命名（例如 `elapsed_ms`、`timeout_sec`），不可使用未標單位的數值。

**百分比、ratio 與時間欄位的表示：**

| 類型 | 範例 | 型別/語意 |
|---|---|---|
| 百分比點 | `drawdown_pct = Decimal("5.0")` | 代表 5%，公式使用前除以 100 |
| ratio | `tolerance_ratio = Decimal("0.05")` | 代表 5%，只能在內部公式使用 |
| RVOL 倍數 | `rvol_ma7 = Decimal("3.0")` | 無單位倍數，不是百分比 |
| timestamp | `slot_ts = 1726876800000` | UTC epoch milliseconds，13 位 `int` |
| duration | `elapsed_ms = 1800000` | 毫秒 `int`；秒數必須命名為 `*_sec` |

**Decimal 與序列化規則：**策略、Candidate、Signal、中間模型、Redis/API payload 禁止 Python `float`。Decimal 在 JSON/Redis 邊界必須使用既定 Decimal encoder/字串格式，禁止由 binary float 隱式轉換。

**Clock 規則：**策略與 Step 的時間只可來自注入的 `Clock`/`StrategyContext.now_ms()`；只有 concrete `SystemClock` 可以呼叫底層 wall clock。

**所有時間戳必須是 13 位毫秒整數**，例如 `1726800000123`。

| 格式               | 位數 | 範例                 | 允許 |
| ------------------ | ---- | -------------------- | :--: |
| 秒（10 位）        | 10   | `1726800000`       |  ❌  |
| 秒（10 位 + 小數） | —   | `1726800000.123`   |  ❌  |
| 毫秒（13 位）      | 13   | `1726800000123`    |  ✅  |
| 微秒（16 位）      | 16   | `1726800000123456` |  ❌  |

**三層防護**：

1. **工具函式**：

**python**

```
   # shared/time_utils.py
   def now_ms() -> int:
       """當前時間（毫秒，13 位整數）"""
       return int(time.time() * 1000)
```

2. **驗證函式**：

**python**

```
def validate_ms(ts: int) -> None:
    """驗證時間戳是 13 位毫秒"""
    if not isinstance(ts, int):
        raise ValidationError("timestamp must be int")
    if ts < 1_000_000_000_000:
        raise ValidationError("timestamp too small, likely seconds")
    if ts > 10_000_000_000_000:
        raise ValidationError("timestamp too large")
```

3. **Prompt 警告** （見第 11.15 節）
   **K 線時間戳規則**
   - K 線時間戳：代表該 K 線的 開盤時間 （幣安原生格式）
   - 5m K 線：00:00, 00:05, 00:10, ...
   - 1h K 線：00:00, 01:00, 02:00, ...
   - 4h K 線：00:00, 04:00, 08:00, 12:00, 16:00, 20:00
   - 1d K 線：00:00 UTC

### 1.6 跨容器資料與通訊權威層級

| 資料類別 | Authoritative source | Redis/快取角色 | 唯一主要 owner |
|---|---|---|---|
| order/trade/audit | MariaDB | pending hot state | executor/order → dbwriter |
| balance/position | Binance | account/position cache | accountsync；order 僅寫穿，accountsync 校正 |
| Candidate terminal state | MariaDB `strategy_candidates` | strategy review state | strategy → dbwriter |
| historical Kline/indicator | ClickHouse | local/Redis cache | kline collectors → dbwriter |
| runtime config | MariaDB | Redis hot cache | dbwriter |

**寫入邊界**：所有 DB INSERT/UPDATE/UPSERT 必須經 `ccurr-dbwriter`；允許的 direct SELECT readers、backtest offline exception 及 Binance public-data exceptions 必須依 Chapter 5/6 matrix 執行。

**Redis unique-writer**：每個 canonical state key 只有一個主要 writer；`position:{symbol}` 是唯一 business-state write-through exception，由 `ccurr-order` 即時寫入、`ccurr-accountsync` 依 Binance 權威結果校正覆寫。`price:latest:{symbol}` 的唯一 primary writer 是 `ccurr-websocket`；`ccurr-trader` 不直接寫入該 canonical key。`trace:{traceId}` 與 `trace:{traceId}:meta` 屬 append-only telemetry，多容器可追加但不屬 canonical business state，禁止以 trace telemetry 覆寫 authoritative state。
**text**

```
shared/
├── config.py                 # BaseServiceSettings
├── errors.py                 # ErrorCode + CcurrError 體系
├── logger.py                 # structlog 初始化
├── models.py                 # KlineRow, Signal, OrderRequest 等
├── redis_keys.py             # Redis Key 集中管理
├── time_utils.py             # 時間對齊工具
├── decimal_utils.py          # Decimal 工具
├── trace/                    # Trace ID 機制
├── locks/                    # 分散式鎖
├── event_bus/                # 事件匯流排
├── audit/                    # 審計日誌
├── degradation/              # 優雅降級
├── dynamic_config/           # 動態配置
├── strategy_log/             # 策略執行記錄
└── uds_client/               # UDS HTTP 客戶端
```

---

## 第 2 章：六大通用機制

### 2.1 Trace ID 追蹤機制

 **目的** ：追蹤一筆交易從「信號產生」到「帳戶更新」的完整鏈路。

 **Canonical model reference**：`Signal` 的唯一規範定義在 [PART05 Chapter 9 §9.4.2](BLUEPRINT-PART05-Chapter09-10-StrategyPluginInterface.md)。本節只說明 Trace ID 所需的欄位，不得建立第二個 Signal schema。


**Signal 欄位示例（非規範；canonical model 見 Chapter 9 §9.4.2）**
    signalId: str
    traceId: str          # 整條鏈的追蹤 ID
    strategyId: str
    # ...
```

 **Redis Key** ：

| Key                      | 類型 | TTL | 用途       |
| ------------------------ | ---- | --- | ---------- |
| `trace:{traceId}:meta` | Hash | 24h | 追蹤元資料 |
| `trace:{traceId}`      | List | 24h | 步驟序列   |

 **模組** ：`shared/trace/`（context / recorder / reader）

 **使用** ：每個容器在處理函式進入時 `set_trace(signal.traceId)`，關鍵步驟呼叫 `trace_recorder.record()`。

---

### 2.2 分散式鎖

 **目的** ：防止多容器同時操作同一資源。

 **實作** ：Redis `SET NX EX` + Lua 釋放。

 **模組** ：`shared/locks/distributed_lock.py`

 **鎖的粒度** ：

| 鎖 Key                          | 保護什麼           | TTL  |
| ------------------------------- | ------------------ | ---- |
| `lock:order:{symbol}`         | 同 symbol 的下單   | 10s  |
| `lock:override:{symbol}`      | 同 symbol 的平倉   | 30s  |
| `lock:bnb_refill`             | BNB 補充           | 60s  |
| `lock:position:{symbol}`      | 持倉寫穿           | 5s   |
| `lock:config:{scope}`         | 配置修改           | 10s  |
| `lock:backfill:{symbol}:{tf}` | 回補               | 600s |
| `lock:symbol_sync`            | Symbol 同步        | 300s |
| `lock:subscription_reconcile` | WebSocket 訂閱對帳 | 60s  |

 **API** ：

**python**

```
lock = DistributedLock(redis, lock_order("BTCUSDT"), ttl_sec=10)
async with lock:
    # 臨界區
    pass
```

**⚠️ 時間戳警告** ：
所有鎖的 TTL 計算與 `now_ms()` 呼叫必須使用 13 位毫秒整數。
禁止直接呼叫 `time.time()`。

---

### 2.3 事件匯流排規範

 **目的** ：統一所有容器的事件格式。

 **事件信封** ：

**python**

```
class EventEnvelope(BaseModel):
    eventId: str              # uuid4
    eventType: str            # order.placed / position.updated
    eventVersion: str         # "1.0"
    source: str               # 發布容器名稱
    ts: int                   # 毫秒
    payload: dict             # 事件資料
    traceId: str | None       # 追蹤 ID
    correlationId: str | None # 關聯 ID
    causationId: str | None   # 因果 ID
    dedupKey: str | None      # 去重鍵
    ttlSec: int | None        # 事件有效期
```

 **事件類型** （節錄）：

**text**

```
signal.generated / signal.received / signal.rejected
order.placing / order.placed / order.filled / order.cancelled
order.timeout_canceled / order.oco_placed
position.opened / position.closed / position.updated
account.synced / balance.updated
risk.checked / risk.rejected / risk.circuit_breaker
override.triggered / override.stage_closed / override.completed
ws.subscription_changed / ws.liquidity_crisis
config.changed
system.degraded / system.recovered
alert.raised
bnb.refill_triggered / bnb.refill_completed / bnb.refill_failed
```

 **模組** ：`shared/event_bus/`（envelope / publisher / subscriber / event_types / channels）

---

### 2.4 審計日誌

 **目的** ：記錄所有使用者操作與系統關鍵操作。

 **MariaDB 表** ：`audit_log`

**sql**

```
CREATE TABLE audit_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id        VARCHAR(64),
    event_type      VARCHAR(64) NOT NULL,
    actor           VARCHAR(64) NOT NULL,
    actor_type      VARCHAR(16) NOT NULL,       -- user / system / auto
    target          VARCHAR(128) NOT NULL,
    action          VARCHAR(32) NOT NULL,       -- create / update / delete / execute
    old_value       JSON,
    new_value       JSON,
    reason          TEXT,
    result          VARCHAR(16) NOT NULL,       -- success / failed / partial
    error_msg       TEXT,
    metadata        JSON,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_trace (trace_id),
    INDEX idx_event_time (event_type, created_at),
    INDEX idx_actor (actor, created_at),
    INDEX idx_target (target, created_at)
);
```

 **模組** ：`shared/audit/logger.py` → `AuditLogger.log()`

 **寫入路徑** ：透過 `ccurr-dbwriter`（sync 模式），失敗時寫本地 fallback。

---

### 2.5 優雅降級矩陣

 **目的** ：某容器掛了，其他容器知道如何反應。

 **降級狀態儲存** ：Redis `system:degradation`（Hash）

 **由 `ccurr-monitor` 維護** ，每 30 秒更新一次。

 **降級矩陣** ：

| 掛掉的容器            | 影響         | 降級行為                   | 告警等級 |
| --------------------- | ------------ | -------------------------- | -------- |
| `ccurr-trader`      | 無法下單     | 停止接受新信號             | critical |
| `ccurr-dbwriter`    | 無法寫 DB    | 寫本地 fallback            | high     |
| `ccurr-accountsync` | 快照過期     | 風控進保守模式             | high     |
| `ccurr-risk`        | 無法風控     | 拒絕正常信號，允許緊急平倉 | critical |
| `ccurr-websocket`   | 無盤口數據   | 策略只用 K 線              | medium   |
| `ccurr-order`       | 訂單不追蹤   | executor 停止下單          | critical |
| `ccurr-override`    | 無法緊急平倉 | 手動操作                   | high     |
| `ccurr-k5m`         | 5m K 線延遲  | 策略跳過 5m                | high     |
| `ccurr-monitor`     | 無監控       | 無影響（只是看不到）       | low      |
| `ccurr-telegram`    | 無法互動     | 無影響                     | low      |
| Redis                 | 全面停擺     | 系統不可用                 | critical |

 **模組** ：`shared/degradation/`（models / reader / matrix / policies）

---

### 2.6 動態配置系統

 **目的** ：所有參數可在 Telegram 動態調整，不需重啟容器。

 **三層結構** ：MariaDB（真相）+ Redis（快取）+ Pub/Sub（事件驅動）

 **MariaDB 表** ：

**sql**

```
CREATE TABLE runtime_config (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    scope           VARCHAR(64) NOT NULL,
    config_key      VARCHAR(64) NOT NULL,
    config_value    VARCHAR(255) NOT NULL,
    value_type      VARCHAR(16) NOT NULL,
    description     VARCHAR(255),
    min_value       VARCHAR(64),
    max_value       VARCHAR(64),
    version         INT DEFAULT 1,
    previous_value  VARCHAR(255),
    changed_by      VARCHAR(64),
    changed_at      DATETIME(3),
    UNIQUE KEY uk_scope_key (scope, config_key)
);

CREATE TABLE runtime_config_history (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    scope           VARCHAR(64),
    config_key      VARCHAR(64),
    version         INT,
    config_value    VARCHAR(255),
    operator        VARCHAR(64),
    reason          TEXT,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    UNIQUE KEY uk_scope_key_version (scope, config_key, version)
);
```

 **Redis Key** ：

| Key                        | 類型    | TTL  | 用途         |
| -------------------------- | ------- | ---- | ------------ |
| `config:{scope}`         | Hash    | 300s | 配置快取     |
| `config:{scope}:version` | String  | 無   | 版本號       |
| `config:changed`         | Pub/Sub | —   | 配置變更事件 |

 **模組** ：`shared/dynamic_config/`（client / watcher / validators / versioning）

 **事件驅動熱重載** ：修改配置後 PUBLISH `config:changed`，容器訂閱後毫秒級生效。

 **Telegram 指令** ：

* `/config {scope}` — 查詢
* `/set_{scope} {key} {value}` — 修改
* `/config_history {scope} {key}` — 歷史
* `/config_rollback {scope} {key} {version}` — 回滾

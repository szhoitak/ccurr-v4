# 第二部：資料層

---

## 第 3 章：資料庫 Schema

### 3.1 ClickHouse

#### 3.1.1 `ccurr.pricesall`

**sql**

```
CREATE TABLE ccurr.pricesall
(
    -- 維度
    `symbol`        String,
    `currency_pair` String,
    `timeframe`     LowCardinality(String),    -- 5m / 1h / 4h / 1d
    `timestamp`     DateTime64(3),

    -- OHLCV
    `open_price`    Decimal(20, 8),
    `high_price`    Decimal(20, 8),
    `low_price`     Decimal(20, 8),
    `close_price`   Decimal(20, 8),
    `volume_base`   Nullable(Decimal(24, 8)),
    `volume_quote`  Nullable(Decimal(24, 8)),

    -- 移動平均
    `ma7`           Nullable(Decimal(16, 8)),
    `ma14`          Nullable(Decimal(16, 8)),
    `ma20`          Nullable(Decimal(20, 8)),
    `ma30`          Nullable(Decimal(16, 8)),
    `ma50`          Nullable(Decimal(16, 8)),
    `ma100`         Nullable(Decimal(20, 8)),
    `ma200`         Nullable(Decimal(20, 8)),

    -- 波動率
    `atr14`         Nullable(Decimal(16, 8)),
    `std20_vol`     Nullable(Decimal(24, 8)),

    -- 動量
    `rsi14`         Nullable(Decimal(6, 2)),
    `macd_line`     Nullable(Decimal(20, 8)),
    `macd_signal`   Nullable(Decimal(20, 8)),
    `macd_histogram` Nullable(Decimal(20, 8)),
    `macd_bullish`  Nullable(Int8),

    -- 趨勢
    `adx14`         Nullable(Decimal(6, 2)),
    `obv`           Nullable(Decimal(24, 4)),
    `obv_trend_up`  Nullable(Int8),

    -- 狀態
    `is_closed`     UInt8 DEFAULT 0,
    `update_at`     DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(update_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timeframe, currency_pair, timestamp)
TTL
    timestamp + toIntervalDay(90)   DELETE WHERE timeframe = '5m',
    timestamp + toIntervalMonth(24) DELETE WHERE timeframe = '1h',
    timestamp + toIntervalYear(5)   DELETE WHERE timeframe = '4h',
    timestamp + toIntervalYear(10)  DELETE WHERE timeframe = '1d'
SETTINGS index_granularity = 8192;
```

#### 3.1.2 `ccurr.symbol_metadata`

**sql**

```
CREATE TABLE ccurr.symbol_metadata
(
    `symbol`                    String,
    `timeframe`                 LowCardinality(String),
    `first_full_indicator_ts`   DateTime64(3),
    `min_bars_required`         UInt32,
    `total_bars`                UInt64,
    `first_bar_ts`              DateTime64(3),
    `last_closed_bar_ts`        DateTime64(3),
    `has_full_indicators`       UInt8,
    `last_updated`              DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(last_updated)
ORDER BY (symbol, timeframe);
```

#### 3.1.3 `ccurr.kline_gaps`

**sql**

```
CREATE TABLE ccurr.kline_gaps
(
    `symbol`        String,
    `timeframe`     LowCardinality(String),
    `gap_start_ts`  DateTime64(3),
    `gap_end_ts`    DateTime64(3),
    `gap_bars`      UInt32,
    `status`        LowCardinality(String),   -- OPEN / FILLED / IGNORED
    `detected_at`   DateTime64(3) DEFAULT now64(3),
    `filled_at`     DateTime64(3),
    `last_updated`  DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(last_updated)
PARTITION BY toYYYYMM(gap_start_ts)
ORDER BY (symbol, timeframe, gap_start_ts);
```

### 3.2 MariaDB

#### 3.2.1 `symbols`

**sql**

```
CREATE TABLE symbols (
    symbol          VARCHAR(32) PRIMARY KEY,
    currency_pair   VARCHAR(32) NOT NULL,
    base_asset      VARCHAR(16),
    quote_asset     VARCHAR(16),
    status          VARCHAR(16),
    listed_at       DATETIME(3),
    enabled         TINYINT(1) DEFAULT 1,
    source          VARCHAR(16) DEFAULT 'binance',
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
);
```

#### 3.2.2 `symbols_blacklist`

**sql**

```
CREATE TABLE symbols_blacklist (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    pattern         VARCHAR(64) NOT NULL,
    match_type      VARCHAR(16) DEFAULT 'exact',   -- exact / prefix / regex
    category        VARCHAR(32),                   -- stablecoin / wrapped / fan_token / leveraged
    reason          TEXT,
    enabled         TINYINT(1) DEFAULT 1,
    created_by      VARCHAR(64),
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);
```

 **預設黑名單** ：穩定幣（USDC/BUSD/FDUSD/TUSD/USDP/DAI/EUR/AEUR）、包裝幣（WBTC/WETH/WBETH）、粉絲幣（PSG/JUV/BAR/ACM/ASR/CITY/INTER/OG/SANTOS/PORTO/LAZIO/ALPINE）、槓桿代幣（BTCUP/BTCDOWN/ETHUP/ETHDOWN）

#### 3.2.3 `order_log`

**sql**

```
CREATE TABLE order_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    client_order_id VARCHAR(64) UNIQUE,
    strategy_id     VARCHAR(64),
    symbol          VARCHAR(32),
    side            ENUM('BUY','SELL'),
    type            VARCHAR(32),
    quantity        DECIMAL(20,8),
    price           DECIMAL(20,8),
    status          VARCHAR(32),
    binance_order_id BIGINT,
    is_maintenance  TINYINT(1) DEFAULT 0,
    request_json    JSON,
    response_json   JSON,
    error_msg       TEXT,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);
```

#### 3.2.4 `trades`

**sql**

```
CREATE TABLE trades (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id        BIGINT,
    client_order_id VARCHAR(64),
    symbol          VARCHAR(32),
    side            ENUM('BUY','SELL'),
    price           DECIMAL(20,8),
    qty             DECIMAL(20,8),
    commission      DECIMAL(20,8),
    commission_asset VARCHAR(16),
    trade_time      DATETIME(3)
);
```

#### 3.2.5 `strategies`

**sql**

```
CREATE TABLE strategies (
    id            VARCHAR(64) PRIMARY KEY,
    name          VARCHAR(128),
    enabled       TINYINT(1) DEFAULT 0,
    mode          VARCHAR(16) DEFAULT 'SEMI',     -- AUTO / SEMI / MANUAL
    params_json   JSON,
    created_at    DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    updated_at    DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
);
```

#### 3.2.6 `strategy_perf`

**sql**

```
CREATE TABLE strategy_perf (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_id   VARCHAR(64),
    snapshot_time DATETIME(3),
    total_pnl     DECIMAL(20,8),
    win_rate      DECIMAL(5,4),
    sharpe        DECIMAL(10,4),
    max_drawdown  DECIMAL(5,4),
    trade_count   INT
);
```

#### 3.2.7 `override_config`

**sql**

```
CREATE TABLE override_config (
    symbol              VARCHAR(32) PRIMARY KEY,
    enabled             TINYINT(1) DEFAULT 1,
    initial_close_pct   INT DEFAULT 50,
    observe_min         INT DEFAULT 15,
    drop_threshold_pct  DECIMAL(5,2) DEFAULT 3.00,
    rise_threshold_pct  DECIMAL(5,2) DEFAULT 3.00,
    second_close_pct    INT DEFAULT 25,
    rebuy_enabled       TINYINT(1) DEFAULT 1,
    rebuy_pct           INT DEFAULT 100,
    updated_at          DATETIME(3)
);
```

#### 3.2.8 `emergency_log`

**sql**

```
CREATE TABLE emergency_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    override_id     VARCHAR(64) UNIQUE,
    symbol          VARCHAR(32),
    event_type      VARCHAR(32),
    close_pct       DECIMAL(5,2),
    total_closed_pct DECIMAL(5,2),
    stage           INT,
    reason          TEXT,
    operator        VARCHAR(64),
    trigger_source  VARCHAR(32),
    price_at_event  DECIMAL(20,8),
    qty_at_event    DECIMAL(20,8),
    status          VARCHAR(32),
    metadata_json   JSON,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);
```

#### 3.2.9 `risk_config` / `risk_history`

**sql**

```
CREATE TABLE risk_config (
    id              INT PRIMARY KEY DEFAULT 1,
    max_risk_per_trade_pct      DECIMAL(5,2) DEFAULT 2.00,
    max_exposure_per_symbol_pct DECIMAL(5,2) DEFAULT 10.00,
    max_total_exposure_pct      DECIMAL(5,2) DEFAULT 50.00,
    max_daily_loss_pct          DECIMAL(5,2) DEFAULT 5.00,
    max_positions               INT DEFAULT 5,
    correlation_threshold       DECIMAL(3,2) DEFAULT 0.80,
    slippage_protection_pct     DECIMAL(5,2) DEFAULT 0.50,
    circuit_breaker_losses      INT DEFAULT 3,
    circuit_breaker_cooldown_min INT DEFAULT 120,
    enabled                     TINYINT(1) DEFAULT 1,
    CHECK (id = 1)
);

CREATE TABLE risk_history (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type      VARCHAR(32),
    rule_id         VARCHAR(8),
    symbol          VARCHAR(32),
    signal_json     JSON,
    reason          TEXT,
    operator        VARCHAR(64),
    created_at      DATETIME(3)
);
```

#### 3.2.10 `telegram_users` / `telegram_log`

**sql**

```
CREATE TABLE telegram_users (
    telegram_id     BIGINT PRIMARY KEY,
    username        VARCHAR(64),
    display_name    VARCHAR(128),
    role            VARCHAR(32) NOT NULL,       -- OWNER / ADMIN / VIEWER
    enabled         TINYINT(1) DEFAULT 1,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    last_active_at  DATETIME(3)
);

CREATE TABLE telegram_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    telegram_id     BIGINT,
    username        VARCHAR(64),
    command         VARCHAR(64),
    args            JSON,
    response        TEXT,
    status          VARCHAR(32),
    error_msg       TEXT,
    created_at      DATETIME(3)
);
```

#### 3.2.11 `strategy_run_log` / `strategy_step_log` / `strategy_error_log`

**sql**

```
CREATE TABLE strategy_run_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id          VARCHAR(64) UNIQUE,
    strategy_id     VARCHAR(64),
    started_at      DATETIME(3),
    finished_at     DATETIME(3),
    status          VARCHAR(16),
    total_symbols   INT,
    passed_step1    INT,
    passed_step2    INT,
    passed_step3    INT,
    passed_step4    INT,
    passed_step5    INT,
    passed_step6    INT,
    candidates      INT,
    errors          INT,
    metadata_json   JSON,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);

CREATE TABLE strategy_step_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id          VARCHAR(64),
    step            VARCHAR(32),
    status          VARCHAR(16),
    count           INT,
    duration_ms     INT,
    metadata_json   JSON,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);

CREATE TABLE strategy_error_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts              DATETIME(3),
    run_id          VARCHAR(64),
    strategy_id     VARCHAR(64),
    step            VARCHAR(32),
    symbol          VARCHAR(32),
    error_type      VARCHAR(64),
    error_msg       TEXT,
    context_json    JSON,
    created_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);
```

#### 3.2.12 `strategy_candidates`

**sql**

```
CREATE TABLE strategy_candidates (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    trace_id                VARCHAR(64) UNIQUE,
    strategy_id             VARCHAR(64),
    symbol                  VARCHAR(32),
    support_type            VARCHAR(16),
    current_price           DECIMAL(20,8),
    support_target_price    DECIMAL(20,8),
    origin_low              DECIMAL(20,8),
    peak_high               DECIMAL(20,8),
    previous_range_high     DECIMAL(20,8),
    drawdown_pct            DECIMAL(5,2),
    profit_potential_pct    DECIMAL(5,2),
    status                  VARCHAR(32),
    review_action           VARCHAR(32),
    review_deadline_ms      BIGINT,
    review_responded_at_ms  BIGINT,
    generated_at            DATETIME(3),
    created_at              DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);
```

#### 3.2.13 `backtest_results`

**sql**

```
CREATE TABLE backtest_results (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id              VARCHAR(64) UNIQUE,
    strategy_id         VARCHAR(64),
    config_json         JSON,
    start_ts            DATETIME(3),
    end_ts              DATETIME(3),
    initial_balance     DECIMAL(20,8),
    final_balance       DECIMAL(20,8),
    total_return_pct    DECIMAL(10,4),
    trade_count         INT,
    win_rate            DECIMAL(5,4),
    profit_factor       DECIMAL(10,4),
    sharpe_ratio        DECIMAL(10,4),
    max_drawdown_pct    DECIMAL(10,4),
    created_at          DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
);
```

#### 3.2.14 `runtime_config` / `runtime_config_history` / `audit_log`

見第 2 章（六大通用機制）。


### 3.3 策略模型與資料庫時間/數值邊界

> **Canonical boundary contract**：策略 domain model、API、Redis 與事件 payload 使用 UTC epoch milliseconds `int`；ClickHouse `DateTime64(3)` 與 MariaDB `DATETIME(3)` 僅為資料庫儲存表示。所有雙向轉換由 persistence/DB adapter 負責，策略模型不得暴露 naive `datetime`。

- DB connection/session timezone 必須固定為 UTC；讀寫 `DateTime64(3)`/`DATETIME(3)` 時保持毫秒精度。
- `generated_at_ms` 對應 `strategy_candidates.generated_at`；`start_ts`/`end_ts` 對應 `backtest_results.start_ts`/`end_ts`。adapter 必須把 13 位毫秒整數轉為 UTC DB datetime，讀回時再轉回 13 位毫秒整數。
- `review_deadline_ms` 與 `review_responded_at_ms` 已是 BIGINT，直接保存 UTC 13 位毫秒整數，仍須呼叫 `validate_ms()`。
- SQL `DECIMAL` 百分比欄位使用百分比點語意，例如 `drawdown_pct = 5.00` 代表 5%，不得在不同層改成 `0.05`。
- DB Decimal 欄位與策略 Decimal 欄位必須保持精度；禁止經由 Python `float` 做中間轉換。
- adapter 必須提供 timestamp/Decimal round-trip test；本節不要求既有 schema migration。

---

## 第 4 章：Redis Key 總表

### 4.1 心跳

| Key                     | TTL | 來源   |
| ----------------------- | --- | ------ |
| `heartbeat:{service}` | 30s | 各容器 |

### 4.2 帳戶與持倉

| Key                        | 類型   | TTL | 來源                |
| -------------------------- | ------ | --- | ------------------- |
| `account:snapshot`       | Hash   | 60s | accountsync         |
| `account:active_symbols` | Set    | 60s | accountsync         |
| `account:open_orders`    | Hash   | 60s | accountsync         |
| `balance:{asset}`        | Hash   | 60s | accountsync         |
| `position:{symbol}`      | Hash   | 60s | order / accountsync |
| `price:latest:{symbol}`  | String | 5s  | websocket         |

### 4.3 訂單

| Key                                    | 類型   | TTL | 來源             |
| -------------------------------------- | ------ | --- | ---------------- |
| `order:pending:{clientOrderId}`      | Hash   | 7d  | executor（建立）/order（更新、終結）         |
| `order:timeout_queue`                | ZSET   | 無  | executor（建立）/order（消費、移除） |
| `order:pending_oco:{entry_order_id}` | Hash   | 7d  | executor（建立）/order（更新、終結）         |
| `trader:order:{clientOrderId}`       | String | 24h | trader（冪等）   |

### 4.4 Signal

| Key                  | 類型    | 說明     |
| -------------------- | ------- | -------- |
| `signal:all`       | Pub/Sub | 正常信號 |
| `signal:emergency` | Pub/Sub | 緊急信號 |

### 4.5 Override

| Key                          | 類型 | TTL  | 來源             |
| ---------------------------- | ---- | ---- | ---------------- |
| `override:state:{symbol}`  | Hash | 7d   | override         |
| `override:active`          | Set  | 無   | override         |
| `override:config:{symbol}` | Hash | 300s | override（快取） |

### 4.6 Risk

| Key             | 類型 | 來源 |
| --------------- | ---- | ---- |
| `risk:state`  | Hash | risk |
| `risk:config` | Hash | risk |

### 4.7 WebSocket

| Key                            | 類型 | TTL | 來源      |
| ------------------------------ | ---- | --- | --------- |
| `ws:mini_ticker:{symbol}`    | Hash | 10s | websocket |
| `ws:book_ticker:{symbol}`    | Hash | 10s | websocket |
| `ws:depth:{symbol}`          | Hash | 10s | websocket |
| `ws:obi:{symbol}`            | Hash | 10s | websocket |
| `ws:big_trade_flow:{symbol}` | Hash | 60s | websocket |
| `ws:liquidity:{symbol}`      | Hash | 10s | websocket |
| `ws:config`                  | Hash | 無  | telegram  |

### 4.8 Strategy

| Key                                | 類型   | TTL | 來源     | 規則 |
| ---------------------------------- | ------ | --- | -------- | ---- |
| `strategy:phase1:{symbol}`       | Hash   | 48h | strategy | |
| `strategy:phase1:active`         | Set    | 無  | strategy | |
| `strategy:cooldown:{symbol}`     | String | 24h | strategy | |
| `strategy:cooldown:active`       | Set    | 無  | strategy | |
| `strategy:pending_reviews`       | ZSET   | 無  | strategy | 僅 SEMI；score=UTC epoch-ms expiry |
| `strategy:candidate_data`        | Hash   | 7d  | strategy | field=trace_id；Candidate JSON；TTL 不代表 terminal |
| `strategy:pending_review:active` | Set    | 無  | strategy | 僅 SEMI `PENDING_REVIEW`；MANUAL 不寫 |
| `telegram:message_map`           | Hash   | 7d  | telegram/strategy | message_id → trace_id |

> **Redis owner contract**：canonical business-state key 只允許唯一主要 writer。`position:{symbol}` 是唯一 business-state write-through 例外：`ccurr-order` 做成交 write-through，`ccurr-accountsync` 每 15 秒依 Binance `/account` 校正覆寫。`price:latest:{symbol}` 唯一由 `ccurr-websocket` 寫入；trace keys 是 append-only telemetry，多容器可追加且不屬 canonical business state。Pending order ownership 固定為：`ccurr-executor` 建立 `order:pending:*`、`order:timeout_queue` 與 `order:pending_oco:*`；`ccurr-order` 只讀取、更新、終結及 recovery/清理，不得重新建立或改變 owner。其他 canonical business-state key 不得由多個業務 writer 競寫。
### 4.9 Trace / Lock / Degradation

| Key                      | 類型   | TTL    |
| ------------------------ | ------ | ------ |
| `trace:{traceId}:meta` | Hash   | 24h    |
| `trace:{traceId}`      | List   | 24h    |
| `lock:*`               | String | 依用途 |
| `system:degradation`   | Hash   | 無     |

### 4.10 Config

| Key                        | 類型    | TTL  |
| -------------------------- | ------- | ---- |
| `config:{scope}`         | Hash    | 300s |
| `config:{scope}:version` | String  | 無   |
| `config:changed`         | Pub/Sub | —   |

### 4.11 BNB Keeper

| Key                        | 類型   | TTL   |
| -------------------------- | ------ | ----- |
| `bnb:last_refill_ms`     | String | 無    |
| `bnb:refill_count_today` | String | 86400 |
| `bnb:refill_failed_ms`   | String | 無    |

### 4.12 Symbol

| Key                           | 類型   | TTL  |
| ----------------------------- | ------ | ---- |
| `symbols:last_sync`         | String | 無   |
| `symbols:cache`             | Hash   | 300s |
| `blacklist:cache`           | Hash   | 300s |
| `symbol_meta:{symbol}:{tf}` | Hash   | 無   |
| `gap:pending:{symbol}:{tf}` | String | 無   |

### 4.13 統計

| Key                   | 類型    | TTL    |
| --------------------- | ------- | ------ |
| `stats:{service}`   | Hash    | 120s   |
| `alert:all`         | Pub/Sub | —     |
| `alert:dedup:{key}` | String  | 依等級 |
| `monitor:history`   | List    | 無     |

### 4.14 Telegram

| Key                                   | 類型   | TTL  |
| ------------------------------------- | ------ | ---- |
| `telegram:users`                    | Hash   | 300s |
| `telegram:pending:{tg_id}:{cmd_id}` | Hash   | 120s |
| `telegram:mute:{tg_id}`             | String | 自訂 |
| `telegram:buffer:{tg_id}`           | List   | 無   |
| `ratelimit:telegram:{tg_id}`        | String | 60s  |
| `telegram:message_map`              | Hash   | 7d   |

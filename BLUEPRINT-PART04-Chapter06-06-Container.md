# 第 6 章：各容器藍圖

> 本章涵蓋 16 個**業務容器**的完整規格（6.1~6.13）、
> 3 個**基礎設施容器**（Redis / MariaDB / ClickHouse，見 6.15 Docker Compose）、
> 與 3 個**運維輔助容器**（6.18 Dozzle / Uptime Kuma / Redis Insight）。
>
> 因篇幅較長，分為五次輸出。

---

## 6.0 容器分類說明

本系統的 Docker 容器分為三類：

| 類別                      | 數量         | 涵蓋章節 | 說明                                         |
| ------------------------- | ------------ | -------- | -------------------------------------------- |
| **業務容器**        | 16           | 6.1~6.13 | 參與交易邏輯（下單、風控、策略、資料採集等） |
| **基礎設施容器**    | 3            | 6.15.2   | Redis / MariaDB / ClickHouse                 |
| **運維輔助容器**    | 3            | 6.18     | Dozzle / Uptime Kuma / Redis Insight         |
| **Docker 容器總數** | **22** | —       | 以上加總                                     |

---

## 第 6 章輸出計畫

| 批次             | 涵蓋容器  | 說明                                                 |
| ---------------- | --------- | ---------------------------------------------------- |
| **第一批** | 6.1~6.5   | trader / dbwriter / accountsync / websocket / k*     |
| 第二批           | 6.6~6.9   | risk / executor / order / override                   |
| 第三批           | 6.10~6.13 | strategy / telegram / monitor / backtest             |
| 第四批           | 6.14~6.15 | 通訊總表更新 + 部署順序                              |
| **第五批** | 6.18      | 運維輔助容器（Dozzle / Uptime Kuma / Redis Insight） |

---

## 6.1 `ccurr-trader`

### 6.1.1 職責

 **幣安唯一出口** 。所有對幣安 REST API 的呼叫都經由它，透過 Tailscale exit node 走 AWS VPS 固定 IP。對內提供 UDS HTTP 服務。

### 6.1.2 對外介面

| 方向 | 介面          | 說明                           |
| ---- | ------------- | ------------------------------ |
| 出   | 幣安 REST API | HTTPS，經 Tailscale → AWS VPS |
| 入   | UDS HTTP      | `/sockets/trader.sock`       |

### 6.1.3 UDS API

| Method | Path                      | 幣安端點           | Weight  | 備註             |
| ------ | ------------------------- | ------------------ | ------- | ---------------- |
| GET    | `/health`               | `/ping`          | 1       |                  |
| POST   | `/order/place`          | `/order`POST     | 1       |                  |
| POST   | `/order/cancel`         | `/order`DELETE   | 1       |                  |
| POST   | `/order/otoco`          | `/orderList/oto` | 1       | 精確參數見 6.7.7 |
| POST   | `/order/oco`            | `/orderList/oco` | 1       | 同上             |
| GET    | `/order/query`          | `/order`GET      | 4       |                  |
| GET    | `/order-list/query`     | `/orderList`     | 4       |                  |
| GET    | `/account/balance`      | `/account`       | 20      |                  |
| GET    | `/account/open-orders`  | `/openOrders`    | 3 或 40 |                  |
| GET    | `/account/all-orders`   | `/allOrders`     | 20      |                  |
| GET    | `/account/my-trades`    | `/myTrades`      | 20      |                  |
| GET    | `/market/price`         | `/ticker/price`  | 2 或 4  |                  |
| GET    | `/market/exchange-info` | `/exchangeInfo`  | 20      |                  |
| GET    | `/market/24h-stats`     | `/ticker/24hr`   | 40      |                  |
| GET    | `/stats`                | —                 | —      |                  |

### 6.1.4 核心功能點

1. **啟動初始化** ：讀 API Key、時間同步
2. **幣安時間同步** ：偏移 > 1s 重新同步
3. **幣安請求簽名** ：HMAC-SHA256
4. **Rate Limit 管理** ：weight-based token bucket
5. **下單** ：冪等性 + 分散式鎖
6. **OTOCO** ：進場 + 停損 + 停利三合一
7. **OCO** ：停損 + 停利
8. **查餘額、未成交訂單、取消訂單**
9. **查最新價、交易對精度**
10. **健康檢查**

### 6.1.5 關鍵約束

* 所有下單必須帶 `clientOrderId`
* 下單失敗不確定狀態 → 回 `status=UNKNOWN`
* OTOCO 的 `workingType` 只支援 `LIMIT`，**禁止 MARKET**
* 私有/交易 REST 只能經由 `ccurr-trader`；`/market/exchange-info` 是 public metadata 的明確例外，accountsync 可直連同步 filters
* `ccurr-trader` 絕不主動查 K 線、絕不寫資料庫；業務 DB writes 一律經 `ccurr-dbwriter`
* 所有請求都必須記 log

### 6.1.6 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.1.7 環境變數

| 變數                       | 說明             | 預設                        |
| -------------------------- | ---------------- | --------------------------- |
| `SERVICE_NAME`           | `ccurr-trader` | —                          |
| `REDIS_HOST`             | Redis 位址       | `ccurr-redis`             |
| `UDS_PATH`               | UDS 路徑         | `/sockets/trader.sock`    |
| `BINANCE_API_KEY`        | 幣安 API Key     | （必填）                    |
| `BINANCE_API_SECRET`     | 幣安 API Secret  | （必填）                    |
| `BINANCE_BASE_URL`       | 幣安位址         | `https://api.binance.com` |
| `BINANCE_RECV_WINDOW_MS` | recvWindow       | `5000`                    |
| `TIME_SYNC_INTERVAL_SEC` | 時間同步間隔     | `300`                     |
| `MAX_WEIGHT_PER_MIN`     | weight 上限      | `1100`                    |
| `MAX_ORDERS_PER_10S`     | 訂單上限         | `45`                      |
| `RETRY_MAX`              | 重試次數         | `3`                       |
| `LOCK_TTL_SEC`           | 下單鎖 TTL       | `10`                      |
| `LOCK_WAIT_SEC`          | 下單鎖等待       | `3.0`                     |

---

## 6.2 `ccurr-dbwriter`

### 6.2.1 職責

 **所有 DB 寫入統一入口** 。避免多容器同時寫 ClickHouse / MariaDB 造成小 part 爆炸或連線數暴增。

### 6.2.2 對外介面

| 方向 | 介面           | 說明                       |
| ---- | -------------- | -------------------------- |
| 入   | UDS HTTP       | `/sockets/dbwriter.sock` |
| 出   | ClickHouse TCP | `ccurr-clickhouse:9000`  |
| 出   | MariaDB TCP    | `ccurr-mariadb:3306`     |
| 出   | Redis          | 寫入統計、錯誤告警         |

### 6.2.3 UDS 端點

| Method | Path                             | 目標                           | 模式            |
| ------ | -------------------------------- | ------------------------------ | --------------- |
| POST   | `/write/kline`                 | ClickHouse`pricesall`        | **async** |
| POST   | `/write/order_log`             | MariaDB`order_log`           | **sync**  |
| POST   | `/write/trade`                 | MariaDB`trades`              | **sync**  |
| POST   | `/write/strategy_perf`         | MariaDB`strategy_perf`       | async           |
| POST   | `/write/emergency_log`         | MariaDB`emergency_log`       | sync            |
| POST   | `/write/telegram_log`          | MariaDB`telegram_log`        | sync            |
| POST   | `/write/audit_log`             | MariaDB`audit_log`           | **sync**  |
| POST   | `/write/runtime_config`        | MariaDB`runtime_config`      | sync            |
| POST   | `/write/symbols/upsert`        | MariaDB`symbols`             | sync            |
| POST   | `/write/symbol_metadata`       | ClickHouse`symbol_metadata`  | sync            |
| POST   | `/write/kline_gaps`            | ClickHouse`kline_gaps`       | sync            |
| POST   | `/write/strategy_run_log`      | MariaDB`strategy_run_log`    | sync            |
| POST   | `/write/strategy_step_log`     | MariaDB`strategy_step_log`   | sync            |
| POST   | `/write/strategy_error_log`    | MariaDB`strategy_error_log`  | sync            |
| POST   | `/write/strategy_candidate`    | MariaDB`strategy_candidates` | sync            |
| POST   | `/update/strategy_candidate`   | MariaDB`strategy_candidates` | sync            |
| POST   | `/write/backtest_result`       | MariaDB`backtest_results`    | sync            |
| GET    | `/read/blacklist`              | MariaDB`symbols_blacklist`   | sync            |
| GET    | `/read/symbols`                | MariaDB`symbols`             | sync            |
| GET    | `/read/audit_log`              | MariaDB`audit_log`           | sync            |
| GET    | `/read/runtime_config`         | MariaDB`runtime_config`      | sync            |
| GET    | `/read/runtime_config_history` | MariaDB                        | sync            |
| GET    | `/read/runtime_config_at_time` | MariaDB                        | sync            |
| GET    | `/read/strategy_errors`        | MariaDB                        | sync            |
| GET    | `/read/strategy_runs`          | MariaDB                        | sync            |
| GET    | `/health`                      | —                             | —              |
| GET    | `/stats`                       | —                             | —              |

### 6.2.4 兩種模式

| 模式            | 適用                     | 行為                         | 回傳                                   |
| --------------- | ------------------------ | ---------------------------- | -------------------------------------- |
| **async** | K 線、績效快照           | 加入佇列即回傳，背景批次寫入 | `{ok: true, queued: true}`           |
| **sync**  | 訂單日誌、成交紀錄、審計 | 阻塞直到寫入成功或失敗       | `{ok: true, written: true, rows: N}` |

### 6.2.5 核心功能點

1. **啟動初始化** ：建立 ClickHouse / MariaDB 連線池
2. **Async 批次寫入 worker** ：累積 1000 筆或 5 秒觸發
3. **Sync 寫入 worker** ：直接寫，用 transaction
4. **背壓保護** ：佇列滿回 `QUEUE_FULL`
5. **重試** ：指數退避 1s → 2s → 4s
6. **Graceful shutdown** ：等待 async queue 清空
7. **版本管理** ：`runtime_config` 自動遞增版本 + 寫入 history
8. **寫入統計**

### 6.2.6 關鍵約束

* 只處理寫入（例外：`/read/*` 是唯讀查詢）
* async 模式可丟資料，sync 模式絕不能丟
* 絕不修改收到的資料
* 所有寫入失敗必須記 log 並告警

### 6.2.7 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.2.8 環境變數

| 變數                 | 說明               | 預設                       |
| -------------------- | ------------------ | -------------------------- |
| `SERVICE_NAME`     | `ccurr-dbwriter` | —                         |
| `UDS_PATH`         | UDS 路徑           | `/sockets/dbwriter.sock` |
| `CLICKHOUSE_HOST`  | ClickHouse 位址    | `ccurr-clickhouse`       |
| `CLICKHOUSE_PORT`  | 埠                 | `9000`                   |
| `MARIADB_HOST`     | MariaDB 位址       | `ccurr-mariadb`          |
| `MARIADB_PORT`     | 埠                 | `3306`                   |
| `ASYNC_BATCH_SIZE` | async 批次大小     | `1000`                   |
| `ASYNC_FLUSH_SEC`  | async 最長等待     | `5`                      |
| `QUEUE_MAX_SIZE`   | 佇列上限           | `50000`                  |
| `RETRY_MAX`        | 重試次數           | `3`                      |

---

## 6.3 `ccurr-accountsync`

### 6.3.1 職責

 **帳戶快照同步 + Symbol 同步 + BNB Keeper** 。

### 6.3.2 對外介面

| 方向 | 介面               | 說明                      |
| ---- | ------------------ | ------------------------- |
| 出   | `ccurr-trader`   | UDS（查餘額、訂單、價格） |
| 出   | 幣安 REST          | HTTPS（查 exchangeInfo）  |
| 出   | `ccurr-dbwriter` | UDS（寫 symbols）         |
| 出   | Redis              | TCP（寫快照、發信號）     |

### 6.3.3 核心功能點

**功能 1：帳戶快照同步（每 15 秒）**

1. 呼叫 trader 查餘額、持倉、未成交訂單
2. 計算總敞口、持倉數、總估值
3. 寫入 Redis：`account:snapshot`、`balance:*`、`position:*`、`account:active_symbols`
4. 發布 `account.synced` 事件

**功能 2：價格刷新（每 5 秒）**

1. 讀當前持倉 symbols
2. 呼叫 trader 查最新價
3. 更新 Redis `position:*` 的 `current_price`

**功能 3：Symbol 同步（每 1 小時）**

1. 呼叫 trader 查 `exchangeInfo`
2. 讀黑名單（從 dbwriter `/read/blacklist`）
3. 過濾：`status=TRADING` + `quote=USDT` + `SPOT` - 黑名單
4. 透過 dbwriter 寫入 MariaDB `symbols`
5. 更新 Redis：
   - `symbols:cache`（Hash 或 String，供 strategy 讀取）
   - `blacklist:cache`（Hash，供 strategy / websocket 讀取）
   - `symbols:last_sync`（時間戳）
6. 發布 `symbols.synced` 事件

**功能 4：BNB Keeper（每 60 秒）**

1. 讀配置（scope=`bnb_keeper`）
2. 檢查 BNB 餘額 < `bnb_low_threshold_usdt`
3. 檢查冷卻、待成交訂單、USDT 餘額
4. 發布補充信號（`strategyId="bnb_keeper"`, `metadata.is_maintenance=true`）

### 6.3.4 Redis Key

| Key                             | 類型   | TTL   | 用途             |
| ------------------------------- | ------ | ----- | ---------------- |
| `account:snapshot`            | Hash   | 60s   | 帳戶總覽         |
| `account:active_symbols`      | Set    | 60s   | 當前持倉 symbols |
| `account:open_orders`         | Hash   | 60s   | 未成交訂單快照   |
| `balance:{asset}`             | Hash   | 60s   | 各資產餘額       |
| `position:{symbol}`           | Hash   | 60s   | 持倉快照（校正） |
| `heartbeat:ccurr-accountsync` | String | 30s   | 心跳             |
| `bnb:last_refill_ms`          | String | 無    | BNB 補充冷卻     |
| `bnb:refill_count_today`      | String | 86400 | 今日補充次數     |

### 6.3.5 關鍵約束

* 絕不直接呼叫幣安下單
* 絕不直接寫 MariaDB / ClickHouse（透過 dbwriter）
* 持倉寫入時不覆蓋 `entry_price`
* Symbol 同步取得 `lock:symbol_sync`
* BNB 補充取得 `lock:bnb_refill`

### 6.3.6 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.3.7 環境變數

| 變數                         | 說明                  | 預設                     |
| ---------------------------- | --------------------- | ------------------------ |
| `SERVICE_NAME`             | `ccurr-accountsync` | —                       |
| `TRADER_UDS_PATH`          | trader UDS 路徑       | `/sockets/trader.sock` |
| `SYNC_INTERVAL_SEC`        | 帳戶同步間隔          | `15`                   |
| `PRICE_REFRESH_SEC`        | 價格刷新間隔          | `5`                    |
| `SYMBOL_SYNC_INTERVAL_SEC` | Symbol 同步間隔       | `3600`                 |
| `BNB_CHECK_INTERVAL_SEC`   | BNB 檢查間隔          | `60`                   |
| `LOCK_SYMBOL_SYNC_TTL_SEC` | Symbol 鎖 TTL         | `300`                  |
| `LOCK_BNB_TTL_SEC`         | BNB 鎖 TTL            | `60`                   |

---

## 6.4 `ccurr-websocket`

### 6.4.1 職責

 **實時行情監控** （WebSocket + OrderBook 分析）。

 **技術選擇** ： **幣安原生 WebSocket** （不用 CCXT Pro，因為訂閱上限 200 vs 1024）

### 6.4.2 對外介面

| 方向 | 介面           | 說明                                                 |
| ---- | -------------- | ---------------------------------------------------- |
| 出   | 幣安 WebSocket | `wss://stream.binance.com:9443/stream`             |
| 出   | 幣安 REST      | `/api/v3/ticker/24hr`                              |
| 入   | Redis          | 讀`position:*`、`blacklist:cache`、`ws:config` |
| 出   | Redis          | 發布`ws:*`頻道與 Key                               |

### 6.4.3 三層數據流架構

| Layer | 監控對象            | 數據流     | 頻率  |
| ----- | ------------------- | ---------- | ----- |
| L1    | 熱門 30 + 持倉      | miniTicker | 1 秒  |
| L1    | 持倉                | bookTicker | 即時  |
| L2    | 持倉 + 前 5 熱門    | depth20    | 100ms |
| L3    | 前 3 熱門（可配置） | aggTrade   | 100ms |

### 6.4.4 動態訂閱

* 用 `SUBSCRIBE` / `UNSUBSCRIBE` 訊息動態調整
* 監控名單 = 熱門幣 ∪ 持倉幣 - 黑名單
* 每 60 秒對帳一次
* 單一 WebSocket 連線承載所有訂閱（上限 1024）

### 6.4.5 計算指標

| 指標                 | 說明                                                      |
| -------------------- | --------------------------------------------------------- |
| **OBI**        | 訂單簿失衡：`(bid_vol - ask_vol) / (bid_vol + ask_vol)` |
| **大單淨流向** | 過去 60 秒大單的主動買 - 主動賣                           |
| **流動性**     | 總深度、價差、滑價、健康度                                |

### 6.4.6 Redis Key 與 Channel

| Key / Channel                  | 類型    | TTL | 用途            |
| ------------------------------ | ------- | --- | --------------- |
| `ws:mini_ticker:{symbol}`    | Hash    | 10s | 最新 miniTicker |
| `ws:book_ticker:{symbol}`    | Hash    | 10s | 最優買賣價      |
| `ws:depth:{symbol}`          | Hash    | 10s | 盤口快照        |
| `ws:obi:{symbol}`            | Hash    | 10s | OBI             |
| `ws:big_trade_flow:{symbol}` | Hash    | 60s | 大單淨流向      |
| `ws:liquidity:{symbol}`      | Hash    | 10s | 流動性          |
| `ws:mini_ticker`             | Pub/Sub | —  | 價格更新事件    |
| `ws:obi:{symbol}`            | Pub/Sub | —  | OBI 更新事件    |
| `ws:big_trade:{symbol}`      | Pub/Sub | —  | 大單即時通知    |
| `ws:liquidity`               | Pub/Sub | —  | 流動性更新      |
| `ws:subscription_changed`    | Pub/Sub | —  | 訂閱變更        |

### 6.4.7 關鍵約束

* 單一 WebSocket 連線承載所有訂閱（上限 1024）
* 動態調整不重建連線
* 斷線自動重連（退避 5 秒），重連後重新對帳訂閱
* **不產生交易信號** （只發布指標）
* 絕不呼叫幣安下單類端點
* 熱門幣排名每 60 秒刷新
* 訂閱對帳每 60 秒執行

### 6.4.8 依賴

`shared/trace`（可選）, `shared/locks`, `shared/event_bus`, `shared/degradation`, `shared/dynamic_config`

### 6.4.9 環境變數

| 變數                           | 說明                | 預設                                     |
| ------------------------------ | ------------------- | ---------------------------------------- |
| `SERVICE_NAME`               | `ccurr-websocket` | —                                       |
| `BINANCE_WS_URL`             | WebSocket 位址      | `wss://stream.binance.com:9443/stream` |
| `BINANCE_REST_URL`           | REST 位址           | `https://api.binance.com`              |
| `TOP_N_VOLUME`               | 熱門幣種數          | `30`                                   |
| `TOP_N_ORDERBOOK`            | L2 熱門數           | `5`                                    |
| `TOP_N_AGGTRADE`             | L3 熱門數           | `3`                                    |
| `VOLUME_REFRESH_SEC`         | 排名刷新間隔        | `60`                                   |
| `SUBSCRIPTION_RECONCILE_SEC` | 訂閱對帳間隔        | `60`                                   |
| `ENABLE_ORDERBOOK`           | 啟用 L2             | `true`                                 |
| `ENABLE_AGGTRADE`            | 啟用 L3             | `false`                                |
| `OBI_DEPTH`                  | OBI 檔位            | `20`                                   |
| `BIG_TRADE_MULTIPLIER`       | 大單倍數            | `20.0`                                 |
| `MIN_TOTAL_DEPTH_USDT`       | 最小深度            | `100000`                               |
| `MAX_SPREAD_PCT`             | 最大價差            | `0.2`                                  |

---

## 6.5 `ccurr-k5m / k1h / k4h / k1d`

### 6.5.1 職責

 **K 線採集 + 指標計算** 。

 **設計原則** ：4 個容器邏輯完全相同，只有 `TIMEFRAME` 環境變數不同。

### 6.5.2 對外介面

| 方向 | 介面               | 說明                                             |
| ---- | ------------------ | ------------------------------------------------ |
| 出   | 幣安 REST          | HTTPS（`/api/v3/klines`，經 macvlan 綁定寬頻） |
| 入   | ClickHouse         | TCP（讀歷史，直連）                              |
| 出   | `ccurr-dbwriter` | UDS（寫 K 線，async）                            |
| 出   | Redis              | TCP（心跳、統計）                                |

### 6.5.3 排程

| Container     | TIMEFRAME | 排程                                 |
| ------------- | --------- | ------------------------------------ |
| `ccurr-k5m` | 5m        | 每 5 分鐘（收盤後 10 秒）            |
| `ccurr-k1h` | 1h        | 每小時（整點後 10 秒）               |
| `ccurr-k4h` | 4h        | **每 1 小時（`minute=10`）** |
| `ccurr-k1d` | 1d        | **每 1 小時（`minute=10`）** |

**為什麼 4h / 1d 改為每 1 小時？**
為了讓「未完成的 4h / 1d K 線」能被策略掃描。`is_closed` + `ReplacingMergeTree(update_at)` 確保最終版本正確。

### 6.5.4 核心功能點

1. **啟動時回補歷史** ：

* 1d：30 根
* 4h：150 根
* 1h：500 根
* 5m：250 根

1. 定時抓取最近 N 根（含當前，強制覆寫）

- 5m：抓 12 根
- 1h：抓 12 根
- 4h：抓 8 根
- 1d：抓 5 根
- 目的：確保「剛收盤的 K 線」被 is_closed=1 覆寫
- 不依賴 watermark 判斷是否重抓

2. **讀 ClickHouse 歷史** （直連）
3. **計算技術指標** ：

* MA7 / MA14 / MA20 / MA30 / MA50 / MA100 / MA200
* ATR14 / RSI14 / ADX14
* OBV / STD20_VOL
* MACD (line/signal/histogram/bullish)
* OBV_TREND_UP

1. **透過 dbwriter 寫入 ClickHouse** （async）
2. **缺口偵測與填補** （用 ClickHouse `neighbor` 函式）
3. **未收盤 K 線重抓**
4. **更新 `symbol_metadata`** （每 N 次抓取一次）
5. **寫心跳、統計**

### 6.5.5 `is_closed` 邏輯

```python
is_closed = 1 if now_ms > kline_close_time_ms + 5000 else 0
```

**為什麼要 5 秒緩衝？**
幣安在 K 線收盤後幾秒內才會標記為「已收盤」。

**⚠️ 關鍵陷阱：必須強制重抓最近 N 根**

**問題**：
若程式只抓「比 watermark 更新的」K 線，則「當前未完成的 K 線」在寫入時 `is_closed=0`。
當這根 K 線真實收盤後，若程式**不再重抓它**，它在 ClickHouse 裡會永遠保持 `is_closed=0`。
結果：策略引擎過濾 `is_closed=1` 時，**永遠漏掉最新完成的那根 K 線**。

**災難情境**：

```text
T=00:00:10 → 抓取，00:00 這根剛開始，寫入 is_closed=0
T=00:01:00 → 策略掃描，Step 2 過濾 is_closed=1 → 00:00 看不到
T=00:05:00 → K 線收盤
T=00:05:10 → 下次抓取，若只抓「新 K 線」
           → 00:00 被視為「舊的」而不重抓
           → 00:00 永遠是 is_closed=0
T=00:06:00 → 策略掃描，00:00 還是看不到
```

**修正規則**：

| Timeframe | 強制重抓根數 |
| --------- | ------------ |
| 5m        | 12           |
| 1h        | 12           |
| 4h        | 8            |
| 1d        | 5            |

**實作邏輯**：

```python
async def fetch_recent_klines(symbol: str, timeframe: str) -> list[Kline]:
    """每次抓取強制重抓最近 N 根（含當前）"""
    n = FORCE_REFETCH_RECENT_BARS[timeframe]
    klines = await binance.get_klines(
        symbol=symbol,
        interval=timeframe,
        limit=n,  # 抓最近 N 根
    )
  
    # 對每根 K 線計算 is_closed
    now = now_ms()
    for k in klines:
        k.is_closed = 1 if now > k.close_time_ms + 5000 else 0
  
    return klines
```

**watermark 的角色**：

- 只用於**回補歷史**判斷（避免重複抓取古老的 K 線）
- **不適用於**「增量更新」（增量更新永遠抓最近 N 根）

**`ReplacingMergeTree(update_at)` 的作用**：

- 同一根 K 線被重抓時，`update_at` 較大者勝出
- 舊的 `is_closed=0` 被新的 `is_closed=1` 自動覆蓋
- 不需手動刪除舊記錄

### 6.5.6 缺口偵測 SQL

```sql
WITH sorted AS (
    SELECT timestamp, neighbor(timestamp, 1) AS next_ts
    FROM ccurr.pricesall FINAL
    WHERE symbol = ? AND timeframe = ? AND is_closed = 1
    ORDER BY timestamp
)
SELECT timestamp AS gap_start, next_ts AS gap_end,
       toUInt32((next_ts - timestamp) / ? - 1) AS gap_bars
FROM sorted
WHERE next_ts - timestamp > ?
```

### 6.5.7 回填流程

1. 查 get_backfill_status（含缺口偵測）
2. 先處理未收盤 K 線（重抓覆蓋）
3. 填補歷史缺口（寫入 kline_gaps 表，狀態 OPEN → FILLED）
4. 回填最新資料（分批抓取，每批 1000 根）
5. 【新增】定時抓取永遠包含「強制重抓最近 N 根」
   - 不依賴 watermark
   - 確保剛收盤的 K 線被 is_closed=1 覆寫

### 6.5.8 Redis Key

| Key                             | 類型   | TTL  | 用途 |
| ------------------------------- | ------ | ---- | ---- |
| `heartbeat:ccurr-k{interval}` | String | 30s  | 心跳 |
| `stats:ccurr-k{interval}`     | Hash   | 120s | 統計 |

### 6.5.9 關鍵約束

* 讀 ClickHouse 直連，寫經 dbwriter
* 指標計算必須用完整歷史視窗（MA200 需要 200 根）
* 只回傳新 K 線的指標
* 過濾未收盤 K 線（`close_time < now`）
* dbwriter 失敗 → 寫本地 fallback
* 啟動時自動補寫 fallback
* 回補取得 `lock:backfill:{symbol}:{tf}`

### 6.5.10 依賴

`shared/trace`（可選）, `shared/locks`, `shared/event_bus`, `shared/degradation`, `shared/dynamic_config`

### 6.5.11 環境變數

| 變數                           | 說明                        | 預設                          |
| ------------------------------ | --------------------------- | ----------------------------- |
| `SERVICE_NAME`               | `ccurr-k5m`等             | —                            |
| `TIMEFRAME`                  | `5m`/`1h`/`4h`/`1d` | （必填）                      |
| `COLLECTOR_INTERVAL`         | 定時抓取間隔（秒）          | 5m:`300`；1h/4h/1d:`3600` |
| `BINANCE_BASE_URL`           | 幣安位址                    | `https://api.binance.com`   |
| `FETCH_LIMIT`                | 增量抓取根數                | `10`                        |
| `BACKFILL_LIMIT`             | 首次回補根數                | `500`                       |
| `HISTORY_LOOKBACK`           | 讀歷史根數                  | 依 timeframe                  |
| `CLICKHOUSE_HOST`            | ClickHouse 位址             | `ccurr-clickhouse`          |
| `DBWRITER_UDS_PATH`          | dbwriter UDS 路徑           | `/sockets/dbwriter.sock`    |
| `MARIADB_HOST`               | MariaDB 位址                | `ccurr-mariadb`             |
| `GAP_DETECTION_ENABLED`      | 啟用缺口偵測                | `true`                      |
| `OPEN_KLINE_REFETCH_ENABLED` | 重抓未收盤 K 線             | `true`                      |
| `LOCK_BACKFILL_TTL_SEC`      | 回補鎖 TTL                  | `600`                       |
| `FORCE_REFETCH_RECENT_BARS`  | 強制重抓最近 N 根           | `依 timeframe（見 6.5.5）`  |
| `FORCE_REFETCH_ENABLED`      | 啟用強制重抓                | `true`                      |

### 6.5.12 macvlan 綁定

```yaml
networks:
  macvlan-net:
    driver: macvlan
    name: macvlan-net
    driver_opts:
      # ⚠️ 注意：這裡的 eth0 必須改成實體機 (CM3588) 實際連網的網卡名稱！
      # 你可以在實體機的終端機輸入 `ip a` 或 `ip link` 來確認 (例如可能是 eth0, enp1s0, end0 等)
      parent: enP4p65s0
    ipam:
      config:
        - subnet: 192.168.200.0/23     # 配合你 RouterOS 的真實網段
          gateway: 192.168.200.1       # 配合你 RouterOS 的真實 Gateway IP

services:
  ccurr-k5m:
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.121
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100  # 權重較低，僅供內部解析 ccurr-redis 使用
  ccurr-k1h:
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.122
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
  ccurr-k4h:
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.123
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
  ccurr-k1d:
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.124
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
  ccurr-trader:
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.120
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
```

 **分配原則** ：

* 5m 權重最高 → 獨立一條寬頻
* 1h / 4h 共用一條
* 1d 最低頻 → 獨立一條
* 以上三點分配已在router os內已完成配署, 只要按上面的ip設定便會自動分流

## 6.6 `ccurr-risk`

### 6.6.1 職責

 **所有下單前的風控守門員** 。 **只讀 Redis** ，絕不呼叫 `ccurr-trader`。

### 6.6.2 對外介面

| 方向 | 介面               | 說明                                            |
| ---- | ------------------ | ----------------------------------------------- |
| 入   | UDS HTTP           | `/sockets/risk.sock`                          |
| 入   | Redis Pub/Sub      | 訂閱`position:updated`、`override:executed` |
| 出   | Redis              | 讀寫`risk:state`、`risk:config`             |
| 出   | `ccurr-dbwriter` | UDS（可選，寫`risk_history`）                 |

### 6.6.3 UDS API

| Method | Path                            | 說明         |
| ------ | ------------------------------- | ------------ |
| POST   | `/risk/check`                 | 風控檢查     |
| GET    | `/risk/state`                 | 查風控狀態   |
| GET    | `/risk/config`                | 查配置       |
| PUT    | `/risk/config`                | 改配置       |
| POST   | `/risk/reset_circuit_breaker` | 手動解除熔斷 |
| GET    | `/health`                     | —           |
| GET    | `/stats`                      | —           |

### 6.6.4 17 條風控規則

| 規則 ID       | 名稱                   | 適用 action      |
| ------------- | ---------------------- | ---------------- |
| R01           | 總開關                 | ALL              |
| R02           | 快照新鮮度             | 開倉類           |
| R03           | 熔斷狀態               | 開倉類           |
| R04           | 持倉存在性             | 平倉類           |
| R05           | 持倉數量上限           | OPEN             |
| R06           | 單筆最大風險           | OPEN             |
| R07           | 單幣最大敞口           | 開倉類           |
| R08           | 總敞口上限             | 開倉類           |
| R09           | 日內最大虧損           | 開倉類           |
| R10           | 相關性限制             | 開倉類           |
| R11           | 滑價保護               | 市價單           |
| R12           | 數量精度               | ALL              |
| R13           | 餘額充足               | OPEN_LONG        |
| R14           | 幣安最小下單量         | ALL              |
| R15           | 流動性檢查             | 開倉類           |
| R16           | 滑價（depth）檢查      | 市價單           |
| **R17** | **資金權重檢查** | **開倉類** |

### 6.6.5 R17 資金權重檢查（V1 canonical sizing）

> `weight_pct` 在 V1 是 **Capital Allocation Weight**，不是 Risk Weight。S/R FLIP 預設 10.0%，ORIGIN_LOW 預設 5.0%。S6 Risk-Parity 是未來版本，不得在 V1 生成。

```text
輸入：
- signal.weight_pct（百分比點）
- signal.strategyId
- strategy_allocation_pct（百分比點）
- account:snapshot.total_usdt_value = total_account_value
- price:latest:{symbol}
- entry_price、stop_limit_price、fee mode

R17：
1. strategy_fund = total_account_value * strategy_allocation_pct / 100
2. trade_amount = strategy_fund * weight_pct / 100
3. original_R17_qty = trade_amount / current_price
4. risk_based_qty =
     (total_account_value * max_risk_per_trade_pct / 100)
     / (entry_price - stop_limit_price)
5. calculated_qty = min(original_R17_qty, risk_based_qty)

R06（最高優先權）：
1. expected_loss = calculated_qty * (entry_price - stop_limit_price)
   + estimated_round_trip_fee
2. actual_risk_pct = expected_loss / total_account_value * 100
3. 若 actual_risk_pct > max_risk_per_trade_pct → DENY

R12 → R14 → R13：
1. R12 以 LOT_SIZE stepSize 向下截斷 calculated_qty；不得向上放大
2. 截斷後重新檢查 minQty/minNotional（R14）
3. required_quote = calculated_qty * entry_price * (1 + fee_rate)
4. required_quote > balance:USDT.free → R13 DENY
5. R14/R13 拒絕時不得送 executor/trader，並寫入 risk_history/strategy_error_log
```

**R06/R12 邊界**：R12 只會減少 quantity，因此不重跑 R06；但截斷後必須重跑 R14。`MIN_NOTIONAL_REJECT` 一律 DENY，禁止自動補大 quantity。所有價格、數量、費用與風險計算使用 Decimal。

**手續費模式**：BNB 使用 0.075% 預留且 OCO safe quantity 以實際 executed quantity 向下 quantize；非 BNB 使用 0.1% 預留，OCO safe quantity = `quantize_down(executed_qty * 0.999, stepSize)`，再重跑 R14。

**輸出 RiskResult**：`allowed`、`calculated_qty`、`risk_amount`、`actual_risk_pct`、`notional`、`rejection_reason`、`rule_id`、`fee_mode`、`risk_version`。Live 的 ccurr-risk 與 Backtest 的 RiskCalculator 必須使用相同公式與拒絕語意。

* **`ccurr-strategy` 負責「意圖」** ：我要買，用 A 區 10% 權重
* **`ccurr-risk` 負責「核算」** ：讀帳戶餘額、策略資金池、當前幣價，算出絕對 qty
* **決策與風控分離**

### 6.6.6 緊急平倉特殊處理

* 只執行 R04、R12、R14
* 跳過其他規則

### 6.6.7 風控狀態結構

**risk: state (Hash)**

```text
HSET risk:state
  daily_pnl_pct           -2.30
  daily_trades            12
  daily_wins              7
  daily_losses            5
  consecutive_losses      2
  consecutive_wins        0
  circuit_breaker         false
  circuit_breaker_until   0
  circuit_breaker_reason  ""
  total_exposure_pct      35.50
  open_positions          3
  last_check_at           1726800000000
  day_start_ms            1726790400000
```

**risk:config (Hash)**

```text
HSET risk:config
  max_risk_per_trade_pct       2.0
  max_exposure_per_symbol_pct  10.0
  max_total_exposure_pct       50.0
  max_daily_loss_pct           5.0
  max_positions                5
  correlation_threshold        0.8
  slippage_protection_pct      0.5
  circuit_breaker_losses       3
  circuit_breaker_cooldown_min 120
  min_snapshot_age_sec         30
  freeze_snapshot_age_sec      300
```

### 6.6.8 關鍵約束

* 絕不呼叫 `ccurr-trader`
* 絕不呼叫幣安
* 風控檢查必須在 10ms 內完成
* Redis 掛了 → 回 `DENY`（保守）
* 熔斷不影響平倉類
* 連續虧損跨日不清零
* 每日 PnL 在 UTC 00:00 清零

### 6.6.9 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.6.10 環境變數

| 變數                               | 說明           | 預設                   |
| ---------------------------------- | -------------- | ---------------------- |
| `SERVICE_NAME`                   | `ccurr-risk` | —                     |
| `UDS_PATH`                       | UDS 路徑       | `/sockets/risk.sock` |
| `REDIS_HOST`                     | Redis 位址     | `ccurr-redis`        |
| `MARIADB_HOST`                   | MariaDB 位址   | `ccurr-mariadb`      |
| `DEFAULT_MAX_RISK_PER_TRADE_PCT` | 單筆風險       | `2.0`                |
| `DEFAULT_MAX_POSITIONS`          | 最大持倉       | `5`                  |
| `DEFAULT_CIRCUIT_BREAKER_LOSSES` | 熔斷筆數       | `3`                  |
| `MIN_SNAPSHOT_AGE_SEC`           | 快照容忍       | `30`                 |
| `FREEZE_SNAPSHOT_AGE_SEC`        | 快照凍結       | `300`                |

---

## 6.7 `ccurr-executor`

### 6.7.1 職責

 **信號執行引擎** （含緊急通道 + 維護通道）。

### 6.7.2 對外介面

| 方向 | 介面               | 說明                                     |
| ---- | ------------------ | ---------------------------------------- |
| 入   | Redis Pub/Sub      | 訂閱`signal:all`、`signal:emergency` |
| 出   | `ccurr-risk`     | UDS（風控檢查）                          |
| 出   | `ccurr-trader`   | UDS（下單、OTOCO）                       |
| 出   | `ccurr-dbwriter` | UDS（寫`order_log`， **sync** ） |
| 出   | Redis              | 寫`order:pending:*`、發事件            |

### 6.7.3 三通道設計

| 通道           | 來源                                      | 風控             | 訂單類型            |
| -------------- | ----------------------------------------- | ---------------- | ------------------- |
| **正常** | `signal:all`                            | 完整風控         | Spot LIMIT / OTO / OTOCO |
| **緊急** | `signal:emergency`                      | 只檢查持倉存在性 | Spot MARKET（不得使用 `reduceOnly`） |
| **維護** | `signal:all`（`is_maintenance=true`） | 跳過風控         | Spot MARKET              |

### 6.7.4 三種 Handler

1. **NormalHandler** ：正常信號處理
2. **EmergencyHandler** ：緊急信號處理（平倉/回購）
3. **MaintenanceHandler** ：維護信號處理（BNB 補充）

### 6.7.5 主迴圈

```text
while True:
    # 優先處理緊急信號（一次清空）
    while emergency_queue 非空:
        處理緊急信號

    # 處理一個正常信號
    try:
        signal = await wait_for(normal_queue.get(), timeout=0.5)
        處理正常信號
    except TimeoutError:
        pass
```

### 6.7.6 正常處理流程

```text
1. set_trace(signal.traceId)
2. 降級檢查
3. 生成 clientOrderId（格式 {strategyId}-{uuid4}）
4. 取得 lock:order:{symbol}
5. 冪等性檢查
6. 呼叫 ccurr-risk（含 R17）
7. 用 risk 回傳的 calculated_qty 建立 OTOCO 請求
8. 呼叫 ccurr-trader POST /order/otoco
9. 若 OTOCO 不支援 → Fallback：
   a. 送 Entry LIMIT 單
   b. 寫入 order:pending_oco:{entry_order_id}
10. 寫 order_log（sync）
11. 寫 order:pending:*（含 created_at_ms、timeout_hours）
12. 寫 order:timeout_queue（ZSET）
13. 發布 order:placed
14. 釋放鎖
```

### 6.7.7 OTO/OTOCO Spot Order Intent 與請求結構

> **產品限制**：本系統只操作 Binance Spot。`reduceOnly` 是 Futures 語意，不得出現在正常或緊急 Spot order request。Strategy Signal/OrderIntent 與 Binance REST request 分離；本節只定義 executor/trader adapter 的 Spot mapping。

```python
class OtocoRequest(BaseModel):
    # Order List identity
    list_client_order_id: str
    entry_client_order_id: str
    tp_client_order_id: str
    sl_client_order_id: str

    # Working order（Entry；OTO/OTOCO 僅允許 LIMIT）
    symbol: str
    strategy_id: str
    trace_id: str
    entry_type: str = "LIMIT"
    entry_side: str = "BUY"
    entry_price: Decimal
    entry_quantity: Decimal

    # Pending order（Entry 完全成交後才啟用）
    pending_side: str = "SELL"
    pending_quantity: Decimal
    tp_price: Decimal
    sl_stop_price: Decimal
    sl_stop_limit_price: Decimal
    time_in_force: str = "GTC"
```

**欄位契約：** `pending_quantity` 是 pending order 的預先指定數量，不能以 `entry_quantity` 隱含代替；partial fill 的 fallback OCO 不使用此固定值，而使用對帳後的實際 `executed_qty`（扣除必要費用預留並經 filters quantize）。

**Order List 語意：**

- OCO：TP 與 SL 同時啟用，一方成交後另一方取消；
- OTO：Entry 完全成交後啟用一個 pending order；
- OTOCO：Entry 完全成交後啟用 TP + SL OCO；
- Spot REST endpoint 由 adapter 依官方版本映射 `/api/v3/orderList/oco`、`/api/v3/orderList/oto`、`/api/v3/orderList/otoco`；實作前仍須以當期官方文件與 exchangeInfo 驗證參數/能力；
- 原子 OTOCO 不可用時，名稱固定為 `Entry + post-fill OCO fallback`。

**ID 契約：** `clientOrderId` 由 `ccurr-executor` 產生，格式 `{strategyId}-{uuid4}`，retry 重用同一值；Binance `orderId`/`orderListId` 只作 exchange identity；`trace_id`、`signal_id`、`client_order_id` 不得互換。

**⚠️ 幣安精確參數名稱對照表**

**端點**：`POST /api/v3/orderList/oto`

| 幣安參數                       | 對應內部欄位              | 值                            | 說明                       |
| ------------------------------ | ------------------------- | ----------------------------- | -------------------------- |
| `symbol`                     | `symbol`                | `BTCUSDT`                   | 交易對                     |
| `listClientOrderId`          | —                        | uuid                          | OTOCO 列表 ID              |
| **`workingType`**      | `entry_type`            | **`LIMIT`**           | 進場單類型（僅支援 LIMIT） |
| `workingSide`                | —                        | `BUY`                       | 進場方向                   |
| `workingClientOrderId`       | `entry_client_order_id` | uuid                          | 進場單 ID                  |
| `workingPrice`               | `entry_price`           | Decimal                       | 進場價                     |
| `workingQuantity`            | `entry_quantity`        | Decimal                       | 進場量                     |
| `workingTimeInForce`         | —                        | `GTC`                       | 進場 TIF                   |
| `pendingSide`                | —                        | `SELL`                      | 出場方向                   |
| `pendingQuantity`            | `pending_quantity`       | Decimal                       | Entry 完全成交後的預先指定出場量 |
| **`pendingAboveType`** | —                        | **`LIMIT_MAKER`**     | 停利單類型                 |
| `pendingAboveClientOrderId`  | `tp_client_order_id`    | uuid                          | 停利單 ID                  |
| `pendingAbovePrice`          | `tp_price`              | Decimal                       | 停利價                     |
| **`pendingBelowType`** | —                        | **`STOP_LOSS_LIMIT`** | 停損單類型                 |
| `pendingBelowClientOrderId`  | `sl_client_order_id`    | uuid                          | 停損單 ID                  |
| `pendingBelowStopPrice`      | `sl_stop_price`         | Decimal                       | 停損觸發價                 |
| `pendingBelowPrice`          | `sl_stop_limit_price`   | Decimal                       | 停損限價                   |
| `pendingBelowTimeInForce`    | —                        | `GTC`                       | 停損 TIF                   |

**⚠️ 實作注意事項**

1. **查閱最新官方文件**：
   幣安 API 參數名稱在不同版本間有調整，實作前必須查閱
   https://binance-docs.github.io/apidocs/spot/en/#new-order-list-oto-trade
2. **禁止使用的值**：

   - `workingType = MARKET` → 幣安拒絕（HTTP 400）
   - `workingType = LIMIT_MAKER` → 幣安拒絕
3. **進場價設定**：
   即使市價已穿價，仍掛高價 LIMIT（撮合引擎會以最優市價成交）。
4. **錯誤處理**：

   - `HTTP 400 Bad Request` → 檢查參數名稱
   - `code = -1102` → 缺少必要參數
   - `code = -2010` → 訂單被拒絕（可能不支援）
5. **Fallback 觸發條件**：
   收到 `HTTP 400` 且 `code` 為 `-2010` 或 `-1102`，視為「不支援 OTOCO」。

 **重要** ：OTOCO 的 `workingType` 只支援 `LIMIT`，即使市價已穿價，仍掛高價 LIMIT（撮合引擎會以最優市價成交）。

### 6.7.8 維護通道差異

| 動作                | 正常 | 維護                      |
| ------------------- | ---- | ------------------------- |
| 呼叫風控            | ✅   | ❌ 跳過                   |
| 寫 order:pending:*  | ✅   | ✅（is_maintenance=1）    |
| 寫 order_log        | ✅   | ✅（標記 is_maintenance） |
| 寫 position:*       | ✅   | ❌                        |
| 寫 trades           | ✅   | ❌                        |
| 發 position:updated | ✅   | ❌                        |

### 6.7.9 Entry + post-fill OCO Fallback 狀態機

> 此 fallback 不是原子 OTOCO：它先提交 Entry，再由 `ccurr-order` 在完全成交或 timeout 後依實際成交量補送 OCO。

```text
ccurr-executor：
1. 嘗試 Spot OTOCO
2. 若 exchangeInfo/REST 回報不支援或拒單 → 送 Entry LIMIT
3. 以 entry_order_id 建立 order:pending:{clientOrderId}
4. 建立 order:pending_oco:{entry_order_id}，保存 TP/SL 計畫、fee policy、retry_count=0、first_attempt_ms
5. 立即釋放，不等待成交

ccurr-order MainLoop/TimeoutLoop：
1. 每 10 秒對帳 Entry
2. NEW → PARTIALLY_FILLED → FILLED
3. timeout 後撤單；executed_qty > 0 時 → TIMEOUT_CANCELED

ccurr-order OcoLoop：
1. 每 10 秒讀 pending_oco 與 Entry 狀態
2. 只有 FILLED/TIMEOUT_CANCELED 且 executed_qty > 0 才補送
3. quantity = executed_qty - 必要手續費預留，依 filters 截斷
4. 小於 min quantity/notional → 保留狀態並告警人工處理
5. OCO 成功才 DEL pending_oco 並發布 order:oco_placed
6. 失敗保留 key，遞增 retry_count；10 次 critical，30 分鐘人工通知
```


### 6.7.10 Redis Key

| Key                                    | 類型   | TTL  | 用途                |
| -------------------------------------- | ------ | ---- | ------------------- |
| `order:pending:{clientOrderId}`      | Hash   | 7d   | 訂單詳情            |
| `order:timeout_queue`                | ZSET   | 無   | 超時延遲佇列        |
| `order:pending_oco:{entry_order_id}` | Hash   | 7d   | Fallback OCO 待補送 |
| `heartbeat:ccurr-executor`           | String | 30s  | 心跳                |
| `stats:ccurr-executor`               | Hash   | 120s | 統計                |

### 6.7.11 `order:pending:*` 結構

```text
HSET order:pending:{clientOrderId}
  client_order_id    signal-uuid-entry
  symbol             BTCUSDT
  status             NEW
  created_at_ms      1726800000000
  timeout_hours      24
  support_type       S_R_FLIP
  executed_qty       0
  strategy_id        volume_breakout_pullback_v1
  trace_id           uuid-v4
  side               BUY
  type               LIMIT
  quantity           0.00307
  price              65650.00
  binance_order_id   123456789
  is_maintenance     0
```

### 6.7.12 關鍵約束

* 所有 Spot 下單必須帶 `clientOrderId`
* `clientOrderId` 由 executor 產生並在 retry 重用；trader 以 `trader:order:{clientOrderId}` 防重
* 本系統不使用 Futures `reduceOnly`；Spot 緊急平倉使用持倉數量與 SELL order
* OTO/OTOCO pending order 只在 working Entry 完全成交後啟用
* fallback OCO 使用對帳後 `executed_qty`，不得使用原始 `entry_quantity`
* OCO 補送成功前不得刪除 `order:pending_oco:*`
* 呼叫 trader 失敗重試 3 次（指數退避）
* `status=UNKNOWN` → 標記待對帳
* dbwriter 失敗 → 寫本地 fallback
* 維護通道不寫 `position:*`、不寫 `trades`

### 6.7.13 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.7.14 環境變數

| 變數                         | 說明               | 預設                       |
| ---------------------------- | ------------------ | -------------------------- |
| `SERVICE_NAME`             | `ccurr-executor` | —                         |
| `TRADER_UDS_PATH`          | trader UDS 路徑    | `/sockets/trader.sock`   |
| `RISK_UDS_PATH`            | risk UDS 路徑      | `/sockets/risk.sock`     |
| `DBWRITER_UDS_PATH`        | dbwriter UDS 路徑  | `/sockets/dbwriter.sock` |
| `ORDER_PENDING_TTL_SEC`    | pending TTL        | `604800`                 |
| `TRADER_RETRY_MAX`         | trader 重試次數    | `3`                      |
| `NORMAL_QUEUE_MAX`         | 正常佇列上限       | `1000`                   |
| `EMERGENCY_QUEUE_MAX`      | 緊急佇列上限       | `100`                    |
| `LOCK_TTL_SEC`             | 下單鎖 TTL         | `10`                     |
| `LOCK_WAIT_SEC`            | 下單鎖等待         | `3.0`                    |
| `MAINTENANCE_STRATEGY_IDS` | 維護策略 ID        | `bnb_keeper`             |

---

## 6.8 `ccurr-order`

### 6.8.1 職責

 **訂單追蹤** （含寫穿機制 + 超時管理 + OCO 補送）。

### 6.8.2 對外介面

| 方向 | 介面               | 說明                                           |
| ---- | ------------------ | ---------------------------------------------- |
| 入   | Redis Pub/Sub      | 訂閱`order:placed`                           |
| 入   | Redis              | 讀`order:pending:*`、`order:timeout_queue` |
| 出   | `ccurr-trader`   | UDS（查訂單、取消、送 OCO）                    |
| 出   | `ccurr-dbwriter` | UDS（寫`trades`， **sync** ）          |
| 出   | Redis              | 寫穿`position:*`、發事件                     |

### 6.8.3 四個獨立迴圈

| 迴圈        | 頻率 | 用途                                  |
| ----------- | ---- | ------------------------------------- |
| MainLoop    | 10s  | 掃描`order:pending:*`，對帳         |
| UnknownLoop | 30s  | 處理`status=UNKNOWN`訂單            |
| TimeoutLoop | 60s  | 處理超時訂單（**ZSET** ）       |
| OcoLoop     | 10s  | 檢查`order:pending_oco:*`，補送 OCO |

 **注意** ：OcoLoop 可與 MainLoop 合併（都是每 10 秒）。

### 6.8.4 寫穿機制

檢測到成交 → 立即更新 Redis position:*（不等 accountsync）

```text
1. 取得 lock:position:{symbol}
2. 讀現有 position
3. 計算新持倉

   - BUY：qty 增加，entry_price 加權平均
   - SELL：qty 減少，entry_price 保留
4. 判斷 event_type（OPENED / CLOSED / INCREASED / DECREASED）
5. 計算 PnL（僅平倉類）
6. 寫 Redis position:{symbol}
7. 發布 position:updated 事件
8. 釋放鎖
```

### 6.8.5 維護訂單跳過

```python
if order.is_maintenance:
   # 只更新 pending 為 DONE
   # 不寫 position、不寫 trades
   return
```

### 6.8.6 超時管理（TimeoutLoop）

```text
【TimeoutLoop 流程】
   
每 60 秒：

1. expired = ZRANGEBYSCORE order:timeout_queue 0 {now_ms}
2. 若 expired 為空 → 結束
3. 對每個 clientOrderId：
   a. 讀 order:pending:{clientOrderId}
   b. 若不存在 → ZREM，跳過
   c. 讀 status：
      - FILLED / CANCELED / EXPIRED / REJECTED → ZREM，跳過
      - NEW / PARTIALLY_FILLED → 繼續
   d. 送 CANCEL（重試 3 次）
   e. 更新 order:pending:* 狀態為 TIMEOUT_CANCELED
   f. 檢查 executed_qty：
      - 若 > 0 → 補送 OCO（用 executed_qty）
      - 若 == 0 → 跳過
   g. 發佈 order:timeout_canceled 事件
   h. 發送 Telegram 通知
   i. ZREM order:timeout_queue {clientOrderId}
```

### 6.8.7 OCO 補送（OcoLoop）

```text
每 10 秒：
1. 掃描 order:pending_oco:*
2. 對每個 entry_order_id：
   a. 讀 order:pending:{entry_order_id}
   b. 若 status 不在 ("FILLED", "TIMEOUT_CANCELED") → 跳過
      - FILLED → 完全成交，需補送 OCO
      - TIMEOUT_CANCELED → 部分成交且超時，需補送 OCO（executed_qty > 0）
      - 其他狀態 → 尚未成交或已取消，跳過
   c. 讀 oco_data = order:pending_oco:{entry_order_id}
   d. 取 executed_qty（若 <= 0 → 跳過）
   e. 呼叫 trader POST /order/oco
   f. 【關鍵】只有收到成功 Response 才 DEL
      - 成功 → DEL order:pending_oco:{entry_order_id}
      - 失敗 → 保留 Key，遞增 retry_count，下次重試
   g. 發 order:oco_placed 事件
```

**⚠️ 關鍵陷阱：OCO 失敗不可刪除 pending_oco**

**問題**：
若呼叫 OCO 失敗（幣安超時、Rate Limit 觸發），
若程式錯誤地執行 `DEL order:pending_oco`，
則**倉位永遠沒有停損保護**。

**災難情境**：

```text
T=0s：Entry 單成交，寫入 order:pending_oco:xxx
T=10s：OcoLoop 檢測到，呼叫 OCO
       → 幣安回 429（Rate Limit）
       → 若程式碼用 try/finally 強制 DEL
       → pending_oco 被刪除
T=20s：OcoLoop 下次掃描，找不到 pending_oco
       → 永遠不會補送 OCO
       → 倉位裸奔！
```

**正確寫法**

```python
async def _process_pending_oco(self, entry_order_id: str) -> None:
    """處理單一 pending_oco"""
    oco_key = f"order:pending_oco:{entry_order_id}"
    oco_data = await self._redis.hgetall(oco_key)
    if not oco_data:
        return
  
    # 1. 讀 Entry 單狀態
    entry_order = await self._redis.hgetall(f"order:pending:{entry_order_id}")
    if not entry_order:
        return

    # ⚠️ 【修正】必須同時允許 FILLED（完全成交）與 TIMEOUT_CANCELED（部分成交且超時）
    # 原因：6.8.6 TimeoutLoop 在部分成交後會把狀態設為 TIMEOUT_CANCELED，
    #       若這裡只允許 FILLED，部分成交的倉位會永遠裸奔
    status = entry_order.get("status")
    if status not in ("FILLED", "TIMEOUT_CANCELED"):
        return
  
    executed_qty = Decimal(entry_order.get("executed_qty", "0"))
    if executed_qty <= 0:
        return
  
    # 2. 呼叫 OCO
    try:
        result = await self._trader.place_oco(OcoRequest(
            symbol=oco_data["symbol"],
            tp_price=Decimal(oco_data["tp_price"]),
            sl_stop_price=Decimal(oco_data["sl_stop_price"]),
            sl_stop_limit_price=Decimal(oco_data["sl_stop_limit_price"]),
            quantity=executed_qty,
        ))
    except Exception as e:
        # 3. 失敗 → 保留 Key，遞增 retry_count
        await self._handle_oco_failure(oco_key, oco_data, str(e))
        return
  
    # 4. 只有成功才 DEL
    if result.ok:
        await self._redis.delete(oco_key)
        log.info("oco_placed",
                 entry_order_id=entry_order_id,
                 symbol=oco_data["symbol"])
    else:
        # API 回 ok=false → 保留 Key
        await self._handle_oco_failure(
            oco_key, oco_data, str(result.error),
        )

async def _handle_oco_failure(
    self,
    oco_key: str,
    oco_data: dict,
    error: str,
) -> None:
    """處理 OCO 失敗"""
    # 1. 遞增 retry_count
    retry_count = int(oco_data.get("retry_count", "0")) + 1
    await self._redis.hset(oco_key, "retry_count", retry_count)
  
    log.error("oco_placement_failed",
              key=oco_key,
              retry_count=retry_count,
              error=error)
  
    # 2. 連續失敗 N 次 → critical 告警
    if retry_count >= OCO_MAX_RETRY:
        await self._publisher.publish_alert(
            level="critical",
            category="oco_placement_failed",
            message=f"OCO 補送連續失敗 {retry_count} 次",
            metadata={
                "entry_order_id": oco_key,
                "symbol": oco_data.get("symbol"),
                "error": error,
            },
        )
  
    # 3. 失敗超過 M 分鐘 → 通知使用者手動掛停損
    first_attempt_ms = int(oco_data.get("first_attempt_ms", "0"))
    if first_attempt_ms == 0:
        await self._redis.hset(oco_key, "first_attempt_ms", now_ms())
    else:
        elapsed_min = (now_ms() - first_attempt_ms) / 60000
        if elapsed_min > OCO_MANUAL_ALERT_MIN:
            await self._publisher.publish_alert(
                level="critical",
                category="oco_manual_intervention",
                message=f"OCO 補送失敗超過 {elapsed_min:.0f} 分鐘，請手動掛停損",
                metadata={
                    "entry_order_id": oco_key,
                    "symbol": oco_data.get("symbol"),
                },
            )
```

**參數**

| 參數                     | 預設 | 說明                          |
| ------------------------ | ---- | ----------------------------- |
| `OCO_MAX_RETRY`        | 10   | 連續失敗 N 次發 critical 告警 |
| `OCO_MANUAL_ALERT_MIN` | 30   | 失敗超過 M 分鐘通知手動干預   |

**order:pending_oco:* `結構（更新）`**

```text
HSET order:pending_oco:{entry_order_id}
  symbol                BTCUSDT
  tp_price              71142.50
  sl_stop_price         62685.00
  sl_stop_limit_price   62058.15
  trace_id              uuid-v4
  strategy_id           volume_breakout_pullback_v1
  created_at_ms         1726800000000
  first_attempt_ms      0                  ← 首次嘗試時間
  retry_count           0                  ← 重試次數
EXPIRE order:pending_oco:{entry_order_id} 604800
```

### 6.8.8 事件發布

* `position:updated`（含 `event_type`、`pnl`、`pnl_pct`）
* `order:filled`
* `order:cancelled`
* `order:timeout_canceled`
* `order:oco_placed`

### 6.8.9 關鍵約束

* 只呼叫 `ccurr-trader`（查訂單、取消、送 OCO）
* 不下單（只取消）
* 寫穿時 `entry_price` 只在加倉時更新
* 寫穿時 `source="order"`
* 部分成交避免重複寫入（追蹤 `last_recorded_qty`）
* 超時後保留 `order:pending:*`（TTL 7 天）供審計
* TimeoutLoop 用 ZSET，不用 SCAN
* OCO 補送失敗必須保留 order:pending_oco（不可 DEL）
* OcoLoop 必須同時處理 FILLED 與 TIMEOUT_CANCELED（部分成交超時）
* 只有收到 OCO 成功 Response 才 DEL
* 連續失敗 10 次發 critical 告警
* 失敗超過 30 分鐘通知手動掛停損
* order:pending_oco 必須記錄 retry_count 與 first_attempt_ms

### 6.8.10 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.8.11 環境變數

| 變數                              | 說明                     | 預設                       |
| --------------------------------- | ------------------------ | -------------------------- |
| `SERVICE_NAME`                  | `ccurr-order`          | —                         |
| `TRADER_UDS_PATH`               | trader UDS 路徑          | `/sockets/trader.sock`   |
| `DBWRITER_UDS_PATH`             | dbwriter UDS 路徑        | `/sockets/dbwriter.sock` |
| `SYNC_INTERVAL_SEC`             | 主輪詢週期               | `10`                     |
| `UNKNOWN_CHECK_INTERVAL_SEC`    | UNKNOWN 檢查週期         | `30`                     |
| `TIMEOUT_CHECK_INTERVAL_SEC`    | 超時檢查週期             | `60`                     |
| `OCO_CHECK_INTERVAL_SEC`        | OCO 補送檢查週期         | `10`                     |
| `ORDER_TIMEOUT_SEC`             | 訂單超時（舊）           | `300`                    |
| `POSITION_WRITETHROUGH_TTL_SEC` | 寫穿 TTL                 | `60`                     |
| `CANCEL_RETRY_MAX`              | 取消重試次數             | `3`                      |
| `CANCEL_RETRY_BACKOFF_SEC`      | 取消重試退避             | `2.0`                    |
| `OCO_MAX_RETRY`                 | OCO 補送連續失敗告警門檻 | `10`                     |
| `OCO_MANUAL_ALERT_MIN`          | OCO 補送失敗手動干預門檻 | `30`                     |

---

## 6.9 `ccurr-override`

### 6.9.1 職責

 **多階段緊急平倉** 。

### 6.9.2 對外介面

| 方向 | 介面               | 說明                                         |
| ---- | ------------------ | -------------------------------------------- |
| 入   | UDS HTTP           | `/sockets/override.sock`                   |
| 出   | Redis              | 發`signal:emergency`                       |
| 出   | `ccurr-dbwriter` | UDS（寫`emergency_log`， **sync** ） |

### 6.9.3 UDS API

| Method | Path                          | 說明         |
| ------ | ----------------------------- | ------------ |
| POST   | `/override/close`           | 啟動平倉     |
| POST   | `/override/cancel`          | 取消         |
| POST   | `/override/force_next`      | 強制下一階段 |
| GET    | `/override/state`           | 查狀態       |
| GET    | `/override/active`          | 查活躍       |
| GET    | `/override/config/{symbol}` | 查配置       |
| PUT    | `/override/config/{symbol}` | 改配置       |
| GET    | `/health`                   | —           |

### 6.9.4 狀態機

```text
IDLE → STAGE_1_EXECUTING → OBSERVING
                              ├── 跌 ≥ threshold → STAGE_2_EXECUTING
                              ├── 漲 ≥ threshold → REBUYING
                              └── 觀察期到 → 延長
```

### 6.9.5 多階段平倉

* **第一階段** ：平 X%（預設 50%）
* **觀察期** ：15 分鐘（可配置）
* **跌 ≥ 3%** ：平 Y%（預設 25%）
* **漲 ≥ 3%** ：回購
* **觀察期到無變化** ：延長 15 分鐘

### 6.9.6 狀態結構

**override:state:{symbol} ( Hash . TTL 7d)**

```text
HSET override:state:BTCUSDT
  status                  OBSERVING
  override_id             uuid-v4
  symbol                  BTCUSDT
  initial_close_pct       50
  total_closed_pct        50
  current_stage           1
  trigger_price           50000.00
  stage1_close_price      50000.00
  stage1_closed_qty       0.001
  observe_started_at      1726800000000
  observe_until           1726800900000
  drop_threshold_pct      3.00
  rise_threshold_pct      3.00
  second_close_pct        25
  rebuy_enabled           1
  rebuy_pct               100
  max_stages              3
  reason                  "SEC 起訴幣安"
  operator                "telegram:123456"
  created_at              1726800000000
```

**override:active ( Set )**

```text
SADD override:active BTCUSDT ETHUSDT
```

**override:config:{symbol} ( Hash . TTL 300s )**

```text
HSET override:config:BTCUSDT
  enabled                 1
  initial_close_pct       50
  observe_min             15
  drop_threshold_pct      3.00
  rise_threshold_pct      3.00
  second_close_pct        25
  rebuy_enabled           1
  rebuy_pct               100
  max_stages              3
```

### 6.9.7 信號格式

**平倉信號（`priority=EMERGENCY`）**

```json
{
    "signalId": "uuid-v4",
    "strategyId": "override",
    "symbol": "BTCUSDT",
    "action": "EMERGENCY_CLOSE",
    "confidence": 1.0,
    "suggestedQty": "0.0005",
    "priority": "EMERGENCY",
    "metadata": {
        "overrideId": "uuid-v4",
        "closePct": 50,
        "stage": 1
    }
}
```

**回購信號（`priority=HIGH`）**

```json
{
    "signalId": "uuid-v4",
    "strategyId": "override",
    "symbol": "BTCUSDT",
    "action": "REBUY",
    "confidence": 1.0,
    "suggestedQty": "0.0005",
    "priority": "HIGH",
    "metadata": {
        "overrideId": "uuid-v4",
        "rebuyPct": 100
    }
}
```

### 6.9.8 核心元件

| 元件                | 職責                                          |
| ------------------- | --------------------------------------------- |
| `StateManager`    | 管理`override:state:*`、`override:active` |
| `ConfigManager`   | 管理`override:config:*`                     |
| `PositionReader`  | 從 Redis 讀持倉與價格                         |
| `SignalPublisher` | 發佈緊急信號                                  |
| `StageExecutor`   | 執行單一平倉階段                              |
| `RebuyExecutor`   | 執行回購                                      |
| `Observer`        | 觀察期主迴圈（每 60 秒）                      |
| `TriggerSource`   | 模式 B 抽象介面（不實作）                     |

### 6.9.9 關鍵約束

* 平倉信號 `priority=EMERGENCY`
* 回購信號 `priority=HIGH`
* 完全獨立於 `ccurr-strategy`
* 模式 B（自動觸發）只留 `TriggerSource` 抽象介面
* 觀察期以「分鐘」為單位，禁用秒
* 平倉取得 `lock:override:{symbol}`
* 所有事件寫 `emergency_log`（透過 dbwriter sync）

### 6.9.10 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.9.11 環境變數

| 變數                           | 說明               | 預設                       |
| ------------------------------ | ------------------ | -------------------------- |
| `SERVICE_NAME`               | `ccurr-override` | —                         |
| `UDS_PATH`                   | UDS 路徑           | `/sockets/override.sock` |
| `DBWRITER_UDS_PATH`          | dbwriter UDS 路徑  | `/sockets/dbwriter.sock` |
| `OVERRIDE_ENABLED`           | 總開關             | `true`                   |
| `DEFAULT_CLOSE_PCT`          | 第一階段比例       | `50`                     |
| `DEFAULT_OBSERVE_MIN`        | 觀察期             | `15`                     |
| `DEFAULT_OBSERVE_EXTEND_MIN` | 延長觀察期         | `15`                     |
| `DEFAULT_DROP_THRESHOLD_PCT` | 跌幅閾值           | `3.0`                    |
| `DEFAULT_RISE_THRESHOLD_PCT` | 回升閾值           | `3.0`                    |
| `DEFAULT_SECOND_CLOSE_PCT`   | 第二階段比例       | `25`                     |
| `DEFAULT_MAX_STAGES`         | 最大階段數         | `3`                      |
| `PRICE_CHECK_INTERVAL_SEC`   | 價格檢查間隔       | `60`                     |
| `LOCK_OVERRIDE_TTL_SEC`      | 平倉鎖 TTL         | `30`                     |
| `LOCK_CONFIG_TTL_SEC`        | 配置鎖 TTL         | `10`                     |
| `STATE_TTL_SEC`              | 狀態 TTL           | `604800`                 |

---

## 6.10 `ccurr-strategy`（概要）

> **完整規格見第 7~10 章** 。本節僅提供容器概要。

### 6.10.1 職責

 **策略引擎** 。三層架構：Layer 1 引擎 / Layer 2 插件 / Layer 3 模式。

### 6.10.2 對外介面

| 方向 | 介面               | 說明                                  |
| ---- | ------------------ | ------------------------------------- |
| 入   | UDS HTTP           | `/sockets/strategy.sock`            |
| 入   | ClickHouse         | TCP（讀 K 線，直連）                  |
| 入   | Redis              | TCP（讀寫狀態、Pub/Sub）              |
| 出   | `ccurr-dbwriter` | UDS（寫策略執行記錄、候選）           |
| 出   | Redis Pub/Sub      | 發布`signal:all`、`telegram:send` |

### 6.10.3 UDS API

| Method | Path                        | 說明             |
| ------ | --------------------------- | ---------------- |
| POST   | `/candidate/confirm`      | 使用者確認候選   |
| POST   | `/candidate/reject`       | 使用者拒絕候選   |
| POST   | `/candidate/manual_enter` | 手動進場         |
| GET    | `/strategy/list`          | 列出所有策略     |
| GET    | `/strategy/{id}`          | 查策略詳情       |
| GET    | `/strategy/{id}/config`   | 查策略配置       |
| PUT    | `/strategy/{id}/config`   | 改策略配置       |
| POST   | `/strategy/{id}/enable`   | 啟用策略         |
| POST   | `/strategy/{id}/disable`  | 停用策略         |
| POST   | `/strategy/reload`        | 重新載入所有策略 |
| GET    | `/candidates`             | 查詢候選清單     |
| GET    | `/candidate/{trace_id}`   | 查單一候選       |
| GET    | `/runs`                   | 查詢執行記錄     |
| GET    | `/run/{run_id}`           | 查單次執行詳情   |
| GET    | `/errors`                 | 查詢錯誤記錄     |
| GET    | `/health`                 | 健康檢查         |
| GET    | `/stats`                  | 統計             |

### 6.10.4 核心功能點

1. **定時掃描** （每 15 分鐘）
2. **載入策略插件** （動態掃描 `plugins/` 目錄）
3. **執行 Step 1~7** （產生候選）
4. **依模式分流** （MANUAL / SEMI / AUTO）
5. **SEMI 超時輪詢** （每 30 秒，用 ZSET）
6. **配置熱重載** （訂閱 `config:changed`）
7. **執行 Step 8** （計算掛單價 + OTOCO 計畫）
8. **記錄執行過程** （`strategy_run_log` 等）
9. **錯誤隔離** （單一策略失敗不影響其他）

### 6.10.5 Redis Key

| Key                                | 類型   | TTL  | 用途                         |
| ---------------------------------- | ------ | ---- | ---------------------------- |
| `strategy:phase1:{symbol}`       | Hash   | 48h  | Phase 1 錨點                 |
| `strategy:phase1:active`         | Set    | 無   | 所有 Phase 1 中 symbol       |
| `strategy:cooldown:{symbol}`     | String | 24h  | 冷卻標記                     |
| `strategy:cooldown:active`       | Set    | 無   | 所有冷卻中 symbol            |
| `strategy:pending_reviews`       | ZSET   | 無   | 待審核（Score = 過期時間戳） |
| `strategy:candidate_data`        | Hash   | 7d   | trace_id → Candidate JSON   |
| `strategy:pending_review:active` | Set    | 無   | 待審核 trace_id              |
| `strategy:candidate:{trace_id}`  | Hash   | 7d   | Candidate 完整資料           |
| `heartbeat:ccurr-strategy`       | String | 30s  | 心跳                         |
| `stats:ccurr-strategy`           | Hash   | 120s | 統計                         |

### 6.10.6 關鍵約束

* 策略代碼零修改支援回測
* 所有時間呼叫用 `self.context.now_ms()`
* 掃描超時 60 秒（`asyncio.wait_for`）
* 序列執行（第一版）
* 配置熱重載用 Pub/Sub（事件驅動）
* Step 1~9 全部由 `BaseStrategy` 子類實作

### 6.10.7 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`, `shared/strategy_log`

### 6.10.8 環境變數

| 變數                         | 說明               | 預設                       |
| ---------------------------- | ------------------ | -------------------------- |
| `SERVICE_NAME`             | `ccurr-strategy` | —                         |
| `UDS_PATH`                 | UDS 路徑           | `/sockets/strategy.sock` |
| `PLUGINS_DIR`              | 插件目錄           | `/app/plugins`           |
| `SCAN_INTERVAL_SEC`        | 掃描間隔           | `900`                    |
| `SCAN_TIMEOUT_SEC`         | 掃描超時           | `60`                     |
| `REVIEW_POLL_INTERVAL_SEC` | 超時輪詢間隔       | `30`                     |
| `DBWRITER_UDS_PATH`        | dbwriter UDS 路徑  | `/sockets/dbwriter.sock` |
| `CLICKHOUSE_HOST`          | ClickHouse 位址    | `ccurr-clickhouse`       |
| `MARIADB_HOST`             | MariaDB 位址       | `ccurr-mariadb`          |

---

## 6.11 `ccurr-telegram`

### 6.11.1 職責

 **人機介面** 。接收 Telegram 指令 → 驗證身份權限 → 路由到對應容器；訂閱 Redis 告警 → 推送給使用者。

### 6.11.2 對外介面

| 方向 | 介面               | 說明                                               |
| ---- | ------------------ | -------------------------------------------------- |
| 入   | Telegram Bot API   | Polling（HTTPS，走 Tailscale）                     |
| 入   | Redis Pub/Sub      | 訂閱`alert:all`、`telegram:send`               |
| 出   | 各容器             | UDS（指令路由）                                    |
| 出   | `ccurr-dbwriter` | UDS（寫 telegram_log、audit_log，**sync** ） |
| 出   | Redis Pub/Sub      | 發布`config:changed`                             |

### 6.11.3 角色分級

| 角色       | 可做                                                   |
| ---------- | ------------------------------------------------------ |
| `OWNER`  | 所有指令                                               |
| `ADMIN`  | 除了「改風控參數、重啟服務、管理使用者」以外的所有指令 |
| `VIEWER` | 只可查詢                                               |

### 6.11.4 指令清單

**查詢類（VIEWER 以上）**

| 指令                              | 說明                  |
| --------------------------------- | --------------------- |
| `/status`                       | 系統整體狀態          |
| `/balance`                      | 帳戶餘額              |
| `/position`                     | 所有持倉              |
| `/position {symbol}`            | 指定 symbol 持倉      |
| `/pnl`                          | 今日/本週/本月 PnL    |
| `/active`                       | 進行中的 override     |
| `/orders`                       | 未成交訂單            |
| `/prices {symbol...}`           | 即時價格              |
| `/health`                       | 各 container 健康狀態 |
| `/config {scope}`               | 查詢配置              |
| `/config_history {scope} {key}` | 配置歷史              |
| `/degradation`                  | 查降級狀態            |
| `/trace {traceId}`              | 查追蹤鏈              |
| `/audit {target}`               | 查審計                |
| `/candidates`                   | 查候選清單            |
| `/candidate {trace_id}`         | 查單一候選            |
| `/runs`                         | 查執行記錄            |
| `/errors`                       | 查錯誤記錄            |

**控制類（ADMIN 以上）**

| 指令                                   | 說明                 |
| -------------------------------------- | -------------------- |
| `/close {symbol} [pct] [reason:...]` | 平倉                 |
| `/close_all`                         | 平倉所有             |
| `/cancel {symbol}`                   | 取消 override        |
| `/force_next {symbol} {action}`      | 強制下一階段         |
| `/enable {target} {id}`              | 啟用策略/override    |
| `/disable {target} {id}`             | 停用策略/override    |
| `/set_{scope} {key} {value}`         | 改配置               |
| `/mute {duration}`                   | 靜音                 |
| `/unmute`                            | 取消靜音             |
| `/blacklist_add {symbol} {category}` | 新增黑名單           |
| `/blacklist_remove {symbol}`         | 移除黑名單           |
| `/symbols_refresh`                   | 手動觸發 symbol 同步 |

**系統類（OWNER 專屬）**

| 指令                          | 說明       |
| ----------------------------- | ---------- |
| `/set_risk {param} {value}` | 改風控參數 |
| `/restart {container}`      | 重啟容器   |
| `/logs {container} {lines}` | 查 log     |
| `/users`                    | 列出白名單 |
| `/add_user {id} {role}`     | 新增使用者 |
| `/remove_user {id}`         | 移除使用者 |

**緊急類（OWNER 專屬）**

| 指令          | 說明         |
| ------------- | ------------ |
| `/panic`    | 緊急全平     |
| `/stop_all` | 停止所有策略 |

**通用**

| 指令                         | 說明              |
| ---------------------------- | ----------------- |
| `/help`                    | 顯示所有指令      |
| `/start`                   | 歡迎訊息          |
| `/ws_config`               | WebSocket 配置    |
| `/ws_set {param} {value}`  | 改 WebSocket 參數 |
| `/bnb_status`              | BNB 狀態          |
| `/bnb_set {param} {value}` | 改 BNB 參數       |

### 6.11.5 二次確認機制

| 指令             | 需要確認 | 確認方式                     |
| ---------------- | -------- | ---------------------------- |
| `/close`       | ✅       | Inline 按鈕                  |
| `/close_all`   | ✅       | Inline 按鈕 + 輸入 "CONFIRM" |
| `/cancel`      | ✅       | Inline 按鈕                  |
| `/force_next`  | ✅       | Inline 按鈕                  |
| `/set_{scope}` | ✅       | Inline 按鈕                  |
| `/restart`     | ✅       | Inline 按鈕 + 輸入 "RESTART" |
| `/stop_all`    | ✅       | Inline 按鈕                  |
| `/panic`       | ❌       | 直接執行（緊急）             |
| 查詢類           | ❌       | 直接執行                     |

### 6.11.6 Inline Keyboard Callback

| Callback Data                         | 動作                             |
| ------------------------------------- | -------------------------------- |
| `confirm:{trace_id}`                | 確認候選                         |
| `reject:{trace_id}`                 | 拒絕候選                         |
| `manual_enter:{trace_id}`           | 手動進場（含價格保護，見 8.4.3） |
| `view_chart:{symbol}`               | 開 TradingView（URL 按鈕）       |
| `view_detail:{trace_id}`            | 查看詳情                         |
| `set_confirm:{scope}:{key}:{value}` | 確認配置修改                     |

### 6.11.7 自訂停利（Telegram Reply）

 **流程** ：

1. Step 7 推送訊息時，將 `message_id → trace_id` 映射寫入 Redis `telegram:message_map`
2. 使用者回覆訊息並輸入數字
3. `ccurr-telegram` 讀取 `reply_to_message.message_id`，查映射得 `trace_id`
4. 呼叫 `ccurr-strategy` UDS `POST /candidate/confirm` 帶 `custom_tp`

### 6.11.8 告警轉發

| Level        | 推送方式                |
| ------------ | ----------------------- |
| `critical` | 立即推送 + 響鈴         |
| `high`     | 立即推送                |
| `medium`   | 合併後推送（每 5 分鐘） |
| `low`      | 只記 log                |

 **靜音模式** ：

* `critical` 仍推送
* `high` / `medium` 存 Redis `telegram:buffer:{tg_id}`
* `unmute` 後一次推送

### 6.11.9 多層防護

1. **網路層** ：Telegram Bot API 走 Tailscale → VPS
2. **身份層** ：Telegram User ID 白名單
3. **權限層** ：角色分級（OWNER / ADMIN / VIEWER）
4. **指令層** ：每個指令有獨立權限要求
5. **確認層** ：高風險指令需二次確認
6. **限流層** ：每分鐘 30 條指令
7. **審計層** ：所有互動寫入 `telegram_log` 與 `audit_log`

### 6.11.10 Redis Key

| Key                                   | 類型   | TTL  | 用途                   |
| ------------------------------------- | ------ | ---- | ---------------------- |
| `telegram:users`                    | Hash   | 300s | 白名單快取             |
| `telegram:pending:{tg_id}:{cmd_id}` | Hash   | 120s | 二次確認               |
| `telegram:mute:{tg_id}`             | String | 自訂 | 靜音到期時間           |
| `telegram:buffer:{tg_id}`           | List   | 無   | 靜音期間告警緩衝       |
| `ratelimit:telegram:{tg_id}`        | String | 60s  | 限流計數               |
| `telegram:message_map`              | Hash   | 7d   | message_id → trace_id |
| `heartbeat:ccurr-telegram`          | String | 30s  | 心跳                   |

### 6.11.11 關鍵約束

* 使用 `python-telegram-bot` v21+， **Polling 模式** （不用 Webhook）
* 只允許私訊，不回群組
* 所有指令必須先檢查白名單與權限
* 高風險指令必須二次確認（Inline 按鈕）
* 所有指令必須限流（每分鐘 30 條）
* 所有互動寫入 `telegram_log`（透過 dbwriter sync）
* 絕不直接呼叫幣安
* 絕不直接寫資料庫（透過 dbwriter）
* 絕不碰交易邏輯
* 訊息用 MarkdownV2 格式
* 訊息超過 4000 字元要分段
* MarkdownV2 發送失敗 → 改用純文字重發
* 修改配置後 PUBLISH `config:changed`（觸發熱重載）

### 6.11.12 依賴

`shared/trace`, `shared/locks`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.11.13 環境變數

| 變數                       | 說明                | 預設                       |
| -------------------------- | ------------------- | -------------------------- |
| `SERVICE_NAME`           | `ccurr-telegram`  | —                         |
| `TELEGRAM_BOT_TOKEN`     | Bot Token           | （必填）                   |
| `TELEGRAM_OWNER_ID`      | 初始 OWNER ID       | （必填）                   |
| `ALERT_CHANNEL`          | 告警頻道            | `alert:all`              |
| `POLLING_TIMEOUT_SEC`    | Polling 超時        | `30`                     |
| `RATE_LIMIT_PER_MIN`     | 每分鐘指令上限      | `30`                     |
| `CONFIRM_TIMEOUT_SEC`    | 二次確認超時        | `120`                    |
| `MEDIUM_ALERT_BATCH_SEC` | medium 告警合併間隔 | `300`                    |
| `MAX_MESSAGE_LEN`        | 單訊息最大長度      | `4000`                   |
| `MARIADB_HOST`           | MariaDB 位址        | `ccurr-mariadb`          |
| `DBWRITER_UDS_PATH`      | dbwriter UDS 路徑   | `/sockets/dbwriter.sock` |

---

## 6.12 `ccurr-monitor`

### 6.12.1 職責

 **監控告警 + 降級維護** 。

### 6.12.2 對外介面

| 方向 | 介面          | 說明                                     |
| ---- | ------------- | ---------------------------------------- |
| 入   | UDS HTTP      | `/sockets/monitor.sock`                |
| 入   | Docker socket | `/var/run/docker.sock`（可選，重啟用） |
| 出   | Redis         | 讀心跳、寫降級狀態、發告警               |

### 6.12.3 UDS API

| Method | Path                     | 說明             |
| ------ | ------------------------ | ---------------- |
| GET    | `/health`              | 所有容器健康狀態 |
| GET    | `/stats`               | 各容器統計       |
| GET    | `/logs/{container}`    | 查 log           |
| POST   | `/restart/{container}` | 重啟（白名單）   |
| GET    | `/alerts/history`      | 告警歷史         |
| POST   | `/alerts/clear_dedup`  | 清除去重         |
| GET    | `/degradation`         | 查降級矩陣       |
| GET    | `/trace/{traceId}`     | 代理 trace 查詢  |

### 6.12.4 四個 Checker

| Checker              | 頻率 | 用途                              |
| -------------------- | ---- | --------------------------------- |
| `HeartbeatChecker` | 30s  | 掃描所有`heartbeat:*`           |
| `StatsChecker`     | 30s  | 檢查佇列、錯誤、weight            |
| `BusinessChecker`  | 30s  | 檢查熔斷、快照過期、override 卡住 |
| `SelfChecker`      | 30s  | 檢查 monitor 自身                 |

### 6.12.5 告警去重

| 等級     | 冷卻時間 |
| -------- | -------- |
| critical | 60s      |
| high     | 5min     |
| medium   | 15min    |
| low      | 1h       |

 **`dedup_key` 格式** ：`{category}:{source}:{target_id}`

### 6.12.6 降級矩陣維護

 **`DegradationMaintainer`** （每 30 秒）：

1. 讀所有心跳狀態
2. 更新 `system:degradation`（Hash）
3. 發布 `system.degraded` / `system.recovered` 事件

 **降級等級** ：

| 等級         | 說明     | 行為           |
| ------------ | -------- | -------------- |
| `ok`       | 正常     | 全功能         |
| `degraded` | 部分功能 | 限制某些操作   |
| `down`     | 不可用   | 完全停止該功能 |

### 6.12.7 監控項目

**心跳監控**

| 監控目標          | 心跳 Key                        | 逾時閾值 | 告警等級 |
| ----------------- | ------------------------------- | -------- | -------- |
| ccurr-trader      | `heartbeat:ccurr-trader`      | 30s      | critical |
| ccurr-dbwriter    | `heartbeat:ccurr-dbwriter`    | 30s      | critical |
| ccurr-k5m         | `heartbeat:ccurr-k5m`         | 15min    | high     |
| ccurr-k1h         | `heartbeat:ccurr-k1h`         | 2h       | high     |
| ccurr-k4h         | `heartbeat:ccurr-k4h`         | 5h       | high     |
| ccurr-k1d         | `heartbeat:ccurr-k1d`         | 25h      | high     |
| ccurr-accountsync | `heartbeat:ccurr-accountsync` | 60s      | high     |
| ccurr-risk        | `heartbeat:ccurr-risk`        | 30s      | critical |
| ccurr-executor    | `heartbeat:ccurr-executor`    | 30s      | critical |
| ccurr-order       | `heartbeat:ccurr-order`       | 60s      | critical |
| ccurr-override    | `heartbeat:ccurr-override`    | 60s      | high     |
| ccurr-strategy    | `heartbeat:ccurr-strategy`    | 60s      | high     |
| ccurr-telegram    | `heartbeat:ccurr-telegram`    | 60s      | high     |
| ccurr-monitor     | `heartbeat:ccurr-monitor`     | 60s      | medium   |

**統計監控**

| 監控目標            | 來源 Key                                     | 條件    | 等級     |
| ------------------- | -------------------------------------------- | ------- | -------- |
| dbwriter async 佇列 | `stats:ccurr-dbwriter.async_queue_len`     | > 40000 | high     |
| dbwriter sync 佇列  | `stats:ccurr-dbwriter.sync_queue_len`      | > 500   | high     |
| executor 正常佇列   | `stats:ccurr-executor.normal_queue_len`    | > 800   | medium   |
| executor 緊急佇列   | `stats:ccurr-executor.emergency_queue_len` | > 50    | critical |
| trader weight       | `stats:ccurr-trader.weight_used_1m`        | > 900   | high     |
| order UNKNOWN 數    | `stats:ccurr-order.unknown_count`          | > 5     | high     |
| override 活躍數     | `override:active`（SCARD）                 | > 3     | high     |

**業務監控**

| 監控目標         | 條件                                   | 等級   |
| ---------------- | -------------------------------------- | ------ |
| 熔斷狀態         | `risk:state.circuit_breaker == true` | high   |
| 快照過期         | `account:snapshot.snapshot_at`> 5min | high   |
| 連續虧損         | `risk:state.consecutive_losses`>= 3  | medium |
| 活躍 override 數 | > 3                                    | high   |
| override 卡住    | 狀態`*_EXECUTING`超過 2 分鐘         | high   |

### 6.12.8 關鍵約束

* Docker 重啟功能預設停用
* 若啟用，必須檢查白名單
* Log 讀取預設停用（第一版）
* 不主動修復服務（只告警）
* 絕不呼叫幣安
* 絕不直接寫資料庫（透過 dbwriter，且預設停用）
* 讀 Redis 用 SCAN 而非 KEYS

### 6.12.9 依賴

`shared/trace`, `shared/event_bus`, `shared/audit`, `shared/degradation`, `shared/dynamic_config`

### 6.12.10 環境變數

| 變數                           | 說明              | 預設                      |
| ------------------------------ | ----------------- | ------------------------- |
| `SERVICE_NAME`               | `ccurr-monitor` | —                        |
| `UDS_PATH`                   | UDS 路徑          | `/sockets/monitor.sock` |
| `DOCKER_ENABLED`             | 是否啟用重啟      | `false`                 |
| `SCAN_INTERVAL_SEC`          | 主掃描週期        | `30`                    |
| `DEGRADATION_UPDATE_SEC`     | 降級更新間隔      | `30`                    |
| `DEDUP_CRITICAL_SEC`         | critical 去重     | `60`                    |
| `DEDUP_HIGH_SEC`             | high 去重         | `300`                   |
| `DEDUP_MEDIUM_SEC`           | medium 去重       | `900`                   |
| `DEDUP_LOW_SEC`              | low 去重          | `3600`                  |
| `RESTART_ALLOWED_CONTAINERS` | 允許重啟清單      | `""`                    |

---

## 6.13 `ccurr-backtest`

### 6.13.1 職責

 **回測引擎** （獨立容器，不參與實盤）。

### 6.13.2 對外介面

| 方向 | 介面       | 說明                       |
| ---- | ---------- | -------------------------- |
| 入   | UDS HTTP   | `/sockets/backtest.sock` |
| 入   | CLI        | 命令列執行                 |
| 入   | ClickHouse | TCP（讀歷史 K 線，offline preload） |
| 入   | MariaDB    | TCP/UDS（讀 offline config；結果經 dbwriter，失敗輸出 `/app/results`） |

### 6.13.3 UDS API

| Method | Path                          | 說明         |
| ------ | ----------------------------- | ------------ |
| POST   | `/backtest/run`             | 執行回測     |
| POST   | `/backtest/sweep`           | 參數掃描     |
| GET    | `/backtest/results`         | 查詢歷史結果 |
| GET    | `/backtest/result/{run_id}` | 查單一結果   |
| GET    | `/health`                   | 健康檢查     |

### 6.13.4 CLI 指令

```bash
# 基本回測

python -m app.main backtest
    --strategy volume_breakout_pullback_v1
    --start 2025-01-01
    --end 2025-06-30
    --symbols BTCUSDT,ETHUSDT,SOLUSDT
    --balance 10000

# 參數掃描

python -m app.main sweep
    --strategy volume_breakout_pullback_v1
    --param threshold_ma7=2.5,3.0,3.5
    --param phase1_min_rise_pct=10,15,20
    --start 2025-01-01
    --end 2025-06-30
```

### 6.13.5 核心元件

| 元件                       | 職責                           |
| -------------------------- | ------------------------------ |
| `BacktestEngine`         | 主引擎                         |
| `VirtualClock`           | 虛擬時鐘                       |
| `HistoricalDataProvider` | 歷史資料提供者（預載入記憶體） |
| `MockBroker`             | 模擬交易所                     |
| `VirtualTimeoutQueue`    | 虛擬超時佇列                   |
| `BacktestContext`        | 回測用的 Context               |
| `PerformanceAnalyzer`    | 績效分析                       |
| `ParameterSweep`         | 參數掃描                       |

### 6.15.7 Deployment readiness and recovery gate

> **唯一 inventory**：22 containers = 16 business + 3 infrastructure + 3 operations。Live 與 backtest 必須使用不同 Compose profile；backtest 不掛載 live sockets、不加入 macvlan、不取得 Binance secrets、不連 Redis/dbwriter。

**Startup layers：**

1. Redis/MariaDB/ClickHouse healthcheck ready；
2. dbwriter/trader ready（DB pools、UDS、Tailscale）；
3. accountsync 對 Binance 完成 boot reconciliation，k*/websocket 啟動；
4. risk/executor/order/override/strategy 啟動，其中 order 先恢復 UNKNOWN/pending OCO；
5. monitor/telegram/operations；backtest 僅在 `--profile backtest` offline 啟動。

**Readiness gate：** `system:degradation=unready/degraded` 且 R02/R03 DENY 所有 OPEN，直到以下條件全部成立：infrastructure healthcheck、MariaDB/Redis/ClickHouse ready、account reconciliation 完成、`account.synced` 已確認、order Main/Unknown recovery 完成、UNKNOWN orders 已被查明/鎖定/認領、以及 pending OCO recovery 完成或明確進入人工處理狀態；CLOSE/EMERGENCY 依可用 trader/fallback 執行。

**Fault policy：** Redis→DENY；dbwriter/MariaDB→retry 3 次後 fallback；trader→禁止 OPEN/保留 UNKNOWN；accountsync→degraded、禁止 OPEN；websocket→R15/R16 禁止 OPEN/市價；telegram→buffer；backtest result DB failure→`/app/results`。



| 項目      | 實盤            | 回測           |
| --------- | --------------- | -------------- |
| 時間      | 真實時間        | 虛擬時鐘       |
| K 線來源  | ClickHouse 直連 | 預載入記憶體   |
| 訂單執行  | 幣安 API        | MockBroker     |
| WebSocket | 實時數據        | 禁用           |
| 人工確認  | SEMI / MANUAL   | 強制 AUTO      |
| 超時機制  | Redis ZSET      | 記憶體虛擬佇列 |
| 外部事件  | 突發新聞        | 假設不存在     |

### 6.13.7 策略代碼零修改

 **實作方式** ：透過依賴注入（Context），策略不知道自己在回測還是實盤。

 **所有策略中的時間呼叫必須改為** ：

```python
# ❌ 錯誤

ts = now_ms()

# ✅ 正確

ts = self.context.now_ms()
```

### 6.13.8 MockBroker 成交邏輯

| 情境                             | 處理                 |
| -------------------------------- | -------------------- |
| LIMIT BUY，`low <= price`      | 以`price`成交      |
| LIMIT SELL，`high >= price`    | 以`price`成交      |
| STOP_LOSS，`low <= stop_price` | 以`stop_price`成交 |
| MARKET                           | 以當前價 ± 滑價成交 |

 **手續費** ：`fee_pct`（預設 0.1%）
 **滑價** ：`slippage_pct`（預設 0.05%）

### 6.13.9 績效指標

| 指標          | 說明                                  |
| ------------- | ------------------------------------- |
| 總報酬率      | `(final - initial) / initial * 100` |
| 交易數        | 總交易筆數                            |
| 勝率          | 獲利筆數 / 總筆數                     |
| Profit Factor | 總獲利 / 總虧損                       |
| 夏普比率      | 年化                                  |
| 最大回撤      | `max((peak - current) / peak)`      |
| 平均持倉時間  | 小時                                  |

### 6.13.10 參數掃描

 **功能** ：

* 對所有參數組合進行回測
* 按總報酬排序
* 輸出比較表

 **過擬合警告** ：

* 訓練集 + 測試集分割（70% / 30%）
* 交叉驗證
* 參數穩定區間
* 樣本外測試

### 6.13.11 輸出格式

| 格式    | 用途                               |
| ------- | ---------------------------------- |
| JSON    | 程式解析                           |
| HTML    | 人類閱讀（含權益曲線圖）           |
| MariaDB | 歷史比較（`backtest_results`表） |

### 6.13.12 關鍵約束

* 獨立容器，**不參與實盤**
* 策略代碼零修改（與 `ccurr-strategy` 共用）
* 預載入記憶體（1 年 200 symbol 約 310 MB）
* 回測強制 AUTO 模式
* 禁用 WebSocket
* 用記憶體虛擬佇列取代 Redis ZSET
* 所有時間呼叫改為 `self.context.now_ms()`

### 6.13.13 依賴

`shared/time_utils`, `shared/models`（可選）
 **不依賴** ：Redis / 幣安 API / UDS client

### 6.13.14 環境變數

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

## 6.14 Container 通訊總表（完整版）

### 6.14.1 UDS 通訊

| 來源                  | 目標               | Socket                     | 用途                       | 模式           |
| --------------------- | ------------------ | -------------------------- | -------------------------- | -------------- |
| `ccurr-accountsync` | `ccurr-trader`   | `/sockets/trader.sock`   | 查餘額、訂單、價格         | sync           |
| `ccurr-executor`    | `ccurr-trader`   | `/sockets/trader.sock`   | 下單、OTOCO、OCO           | sync           |
| `ccurr-executor`    | `ccurr-risk`     | `/sockets/risk.sock`     | 風控檢查                   | sync           |
| `ccurr-executor`    | `ccurr-dbwriter` | `/sockets/dbwriter.sock` | 寫 order_log               | **sync** |
| `ccurr-order`       | `ccurr-trader`   | `/sockets/trader.sock`   | 查訂單、取消、送 OCO       | sync           |
| `ccurr-order`       | `ccurr-dbwriter` | `/sockets/dbwriter.sock` | 寫 trades                  | **sync** |
| `ccurr-override`    | `ccurr-dbwriter` | `/sockets/dbwriter.sock` | 寫 emergency_log           | **sync** |
| `ccurr-strategy`    | `ccurr-dbwriter` | `/sockets/dbwriter.sock` | 寫策略記錄、候選           | sync           |
| `ccurr-telegram`    | `ccurr-override` | `/sockets/override.sock` | 平倉、取消、查配置         | sync           |
| `ccurr-telegram`    | `ccurr-strategy` | `/sockets/strategy.sock` | 確認/拒絕候選、改配置      | sync           |
| `ccurr-telegram`    | `ccurr-risk`     | `/sockets/risk.sock`     | 查風控狀態、改參數         | sync           |
| `ccurr-telegram`    | `ccurr-trader`   | `/sockets/trader.sock`   | 查餘額、持倉、價格         | sync           |
| `ccurr-telegram`    | `ccurr-monitor`  | `/sockets/monitor.sock`  | 查健康、重啟、查 log       | sync           |
| `ccurr-telegram`    | `ccurr-dbwriter` | `/sockets/dbwriter.sock` | 寫 telegram_log、audit_log | sync           |
| `ccurr-monitor`     | `ccurr-dbwriter` | `/sockets/dbwriter.sock` | 寫監控歷史（可選）         | sync           |

### 6.14.2 外部 API 呼叫

| 來源                            | 目標             | 協定  | 用途                                      |
| ------------------------------- | ---------------- | ----- | ----------------------------------------- |
| `ccurr-trader`                | Binance private/trading REST | HTTPS | 下單、取消、查帳戶/訂單（不查 K 線） |
| `ccurr-k5m / k1h / k4h / k1d` | Binance public REST        | HTTPS | 抓 K 線（macvlan 綁寬頻） |
| `ccurr-accountsync`           | Binance public REST        | HTTPS | 查 exchangeInfo（public exception） |
| `ccurr-websocket`             | Binance public WebSocket   | WSS   | 訂閱行情 |
| `ccurr-websocket`             | Binance public REST        | HTTPS | 熱門幣排名 |
| `ccurr-telegram`              | Telegram Bot API | HTTPS | Polling + 發送訊息 |
| `ccurr-k*`                    | ClickHouse       | TCP   | 讀歷史（直連） |
| `ccurr-k*`                    | MariaDB          | TCP   | 讀 symbols（唯讀） |
| `ccurr-strategy`              | ClickHouse       | TCP   | 讀 K 線（直連） |
| `ccurr-strategy`              | MariaDB          | TCP   | 讀配置（唯讀） |
| `ccurr-risk`                  | MariaDB          | TCP   | 讀 risk_config（唯讀） |
| `ccurr-override`              | MariaDB          | TCP   | 讀 override_config（唯讀） |
| `ccurr-backtest`              | ClickHouse       | TCP   | 讀歷史 K 線（offline） |
| `ccurr-backtest`              | `/app/results`   | filesystem | 寫 JSON/HTML 回測結果；不連 dbwriter、不進 live DB write path |
| `ccurr-dbwriter`              | ClickHouse       | TCP   | 寫 pricesall、symbol_metadata、kline_gaps |
| `ccurr-dbwriter`              | MariaDB          | TCP   | 寫 order_log、trades、audit_log 等

### 6.14.3 Redis event reliability

> Pub/Sub is best-effort only. Reliable channels require state/DB persistence and the recovery loops below.

- Lossy: `ws:*`, heartbeat/stats, async kline/perf, low alerts.
- Reliable: `signal:*`, `order:*`, `position:updated`, `account.synced`, `override:executed`, config/degradation, high/critical alerts.
- Missing signal: strategy checks approved state vs pending orders every 30s and re-publishes after 60s with the same idempotency key.
- Missing order event: ccurr-order scans pending orders every 10s.
- Missing position event: risk pulls position state; accountsync corrects from Binance every 15s.



| Channel                     | 發布者                                           | 訂閱者                                  | 用途               |
| --------------------------- | ------------------------------------------------ | --------------------------------------- | ------------------ |
| `signal:all`              | `ccurr-strategy`、`ccurr-accountsync`（BNB） | `ccurr-executor`                      | 正常信號           |
| `signal:emergency`        | `ccurr-override`                               | `ccurr-executor`                      | 緊急信號           |
| `order:placed`            | `ccurr-executor`                               | `ccurr-order`                         | 新訂單通知         |
| `order:filled`            | `ccurr-order`                                  | `ccurr-telegram`、`ccurr-monitor`   | 訂單成交           |
| `order:cancelled`         | `ccurr-order`                                  | `ccurr-telegram`                      | 訂單取消           |
| `order:timeout_canceled`  | `ccurr-order`                                  | `ccurr-telegram`                      | 超時取消           |
| `order:oco_placed`        | `ccurr-order`                                  | `ccurr-telegram`                      | OCO 補送完成       |
| `position:updated`        | `ccurr-order`                                  | `ccurr-risk`、`ccurr-telegram`      | 持倉變化           |
| `position:updated`        | `ccurr-accountsync`                            | `ccurr-risk`、`ccurr-telegram`      | 持倉校正           |
| `account.synced`          | `ccurr-accountsync`                            | `ccurr-risk`、`ccurr-monitor`       | 帳戶同步           |
| `override:executed`       | `ccurr-override`                               | `ccurr-risk`                          | 緊急平倉完成       |
| `config:changed`          | `ccurr-telegram`                               | `ccurr-strategy`、`ccurr-websocket` | 配置變更           |
| `ws:mini_ticker`          | `ccurr-websocket`                              | `ccurr-strategy`                      | 價格更新事件       |
| `ws:obi:{symbol}`         | `ccurr-websocket`                              | `ccurr-strategy`                      | OBI 更新事件       |
| `ws:big_trade:{symbol}`   | `ccurr-websocket`                              | `ccurr-strategy`                      | 大單即時通知       |
| `ws:liquidity`            | `ccurr-websocket`                              | `ccurr-strategy`、`ccurr-risk`      | 流動性更新事件     |
| `ws:subscription_changed` | `ccurr-websocket`                              | `ccurr-monitor`                       | 訂閱變更           |
| `system:degradation`      | `ccurr-monitor`                                | 全部容器                                | 降級狀態變更       |
| `alert:all`               | 全部容器                                         | `ccurr-telegram`、`ccurr-monitor`   | 告警               |
| `telegram:send`           | `ccurr-strategy`、`ccurr-override`           | `ccurr-telegram`                      | 發送 Telegram 訊息 |

### 6.14.4 Redis Key 讀寫總表

| Key                                    | 寫入者                                                 | 讀取者                                                                                         |
| -------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `heartbeat:{service}`                | 各容器                                                 | `ccurr-monitor`                                                                              |
| `stats:{service}`                    | 各容器                                                 | `ccurr-monitor`                                                                              |
| `account:snapshot`                   | `ccurr-accountsync`                                  | `ccurr-risk`、`ccurr-strategy`、`ccurr-telegram`                                         |
| `account:active_symbols`             | `ccurr-accountsync`                                  | `ccurr-risk`                                                                                 |
| `account:open_orders`                | `ccurr-accountsync`                                  | `ccurr-risk`、`ccurr-telegram`                                                             |
| `balance:{asset}`                    | `ccurr-accountsync`                                  | `ccurr-risk`、`ccurr-telegram`                                                             |
| `position:{symbol}`                  | `ccurr-order`（寫穿）、`ccurr-accountsync`（校正） | `ccurr-risk`、`ccurr-executor`、`ccurr-strategy`、`ccurr-override`、`ccurr-telegram` |
| `price:latest:{symbol}`              | `ccurr-websocket`（唯一 primary writer）       | `ccurr-risk`、`ccurr-executor`、`ccurr-strategy`                                         |
| `order:pending:{clientOrderId}`      | `ccurr-executor`（建立）；`ccurr-order`（更新、終結、recovery） | `ccurr-order`                                                                                |
| `order:timeout_queue`                | `ccurr-executor`（建立）；`ccurr-order`（消費、移除） | `ccurr-order`                                                                                |
| `order:pending_oco:{entry_order_id}` | `ccurr-executor`（建立）；`ccurr-order`（更新、終結、recovery） | `ccurr-order`                                                                                |
| `trader:order:{clientOrderId}`       | `ccurr-trader`                                       | `ccurr-trader`                                                                               |
| `override:state:{symbol}`            | `ccurr-override`                                     | `ccurr-override`、`ccurr-telegram`                                                         |
| `override:active`                    | `ccurr-override`                                     | `ccurr-override`、`ccurr-monitor`、`ccurr-telegram`                                      |
| `override:config:{symbol}`           | `ccurr-override`                                     | `ccurr-override`                                                                             |
| `risk:state`                         | `ccurr-risk`                                         | `ccurr-risk`、`ccurr-telegram`、`ccurr-monitor`                                          |
| `risk:config`                        | `ccurr-risk`                                         | `ccurr-risk`、`ccurr-telegram`                                                             |
| `ws:mini_ticker:{symbol}`            | `ccurr-websocket`                                    | `ccurr-strategy`、`ccurr-telegram`                                                         |
| `ws:obi:{symbol}`                    | `ccurr-websocket`                                    | `ccurr-strategy`                                                                             |
| `ws:liquidity:{symbol}`              | `ccurr-websocket`                                    | `ccurr-strategy`、`ccurr-risk`                                                             |
| `ws:config`                          | `ccurr-telegram`                                     | `ccurr-websocket`                                                                            |
| `strategy:phase1:{symbol}`           | `ccurr-strategy`                                     | `ccurr-strategy`                                                                             |
| `strategy:phase1:active`             | `ccurr-strategy`                                     | `ccurr-strategy`                                                                             |
| `strategy:cooldown:{symbol}`         | `ccurr-strategy`                                     | `ccurr-strategy`                                                                             |
| `strategy:pending_reviews`           | `ccurr-strategy`                                     | `ccurr-strategy`                                                                             |
| `strategy:candidate_data`            | `ccurr-strategy`                                     | `ccurr-strategy`                                                                             |
| `trace:{traceId}:meta`               | 全部容器（append-only telemetry）                    | `ccurr-telegram`、`ccurr-monitor`                                                          |
| `trace:{traceId}`                    | 全部容器（append-only telemetry）                    | `ccurr-telegram`、`ccurr-monitor`                                                          |
| `lock:*`                             | 全部容器                                               | 全部容器                                                                                       |
| `system:degradation`                 | `ccurr-monitor`                                      | 全部容器                                                                                       |
| `config:{scope}`                     | `ccurr-dbwriter`（由 telegram 觸發）                 | 全部容器                                                                                       |
| `config:{scope}:version`             | `ccurr-dbwriter`                                     | 全部容器                                                                                       |
| `bnb:last_refill_ms`                 | `ccurr-accountsync`                                  | `ccurr-accountsync`                                                                          |
| `bnb:refill_count_today`             | `ccurr-accountsync`                                  | `ccurr-accountsync`                                                                          |
| `symbols:cache`                      | `ccurr-accountsync`                                  | `ccurr-strategy`                                                                             |
| `blacklist:cache`                    | `ccurr-accountsync`                                  | `ccurr-strategy`、`ccurr-websocket`                                                        |
| `alert:dedup:{key}`                  | `ccurr-monitor`                                      | `ccurr-monitor`                                                                              |
| `monitor:history`                    | `ccurr-monitor`                                      | `ccurr-monitor`、`ccurr-telegram`                                                          |
| `telegram:users`                     | `ccurr-telegram`                                     | `ccurr-telegram`                                                                             |
| `telegram:pending:{tg_id}:{cmd_id}`  | `ccurr-telegram`                                     | `ccurr-telegram`                                                                             |
| `telegram:mute:{tg_id}`              | `ccurr-telegram`                                     | `ccurr-telegram`                                                                             |
| `telegram:buffer:{tg_id}`            | `ccurr-telegram`                                     | `ccurr-telegram`                                                                             |
| `ratelimit:telegram:{tg_id}`         | `ccurr-telegram`                                     | `ccurr-telegram`                                                                             |
| `telegram:message_map`               | `ccurr-telegram`                                     | `ccurr-telegram`                                                                             |

---

### 6.14.3 DB/事件/恢復 ownership contract

- 所有 DB INSERT/UPDATE/UPSERT 必須經 `ccurr-dbwriter`；ClickHouse direct SELECT readers 為 strategy/k*/backtest，MariaDB direct SELECT readers 為 strategy/risk/override/k*/backtest；executor/trader/telegram 不直連 DB。
- lossy：ws 指標、heartbeat/stats、async kline、strategy_perf、low alerts；可遺失，最新值優先。
- reliable：signal、order lifecycle、position/account sync、config/degradation、high/critical alerts；以 state/DB、retry/idempotency、reconciliation 保底。
- accountsync：boot/15s 對帳 account/balance/position/openOrders；order：10s MainLoop、30s UnknownLoop、10s OcoLoop。
- Crash window：UNKNOWN 重用 clientOrderId 查 `/order`，不得直接重下；pending OCO 成功前不得刪除，失敗 10 次/30 分鐘告警。
- backtest 是 offline sandbox：啟動資料/config fatal、sweep 單組合可隔離、結果一律寫 `/app/results`，不依賴 Redis、dbwriter 或 live DB write path。



### 6.15.1 啟動順序

```text
第 1 層：基礎設施
  ├── ccurr-redis
  ├── ccurr-mariadb
  └── ccurr-clickhouse

第 2 層：核心服務
  ├── ccurr-trader
  └── ccurr-dbwriter

第 3 層：資料服務
  ├── ccurr-accountsync
  ├── ccurr-websocket
  └── ccurr-k5m / k1h / k4h / k1d

第 4 層：決策與執行
  ├── ccurr-risk
  ├── ccurr-executor
  ├── ccurr-order
  ├── ccurr-override
  └── ccurr-strategy

第 5 層：介面與監控
  ├── ccurr-telegram
  └── ccurr-monitor

獨立：
  └── ccurr-backtest（不參與實盤）
```

### 6.15.2 Docker Compose（完整範例）

```yaml
# ============================================================
# ccurr 全自動加密貨幣量化交易系統
# Docker Compose v3.9
# ============================================================
# 最後更新：2026-09-28
# 版本：v1.0
#
# 架構說明：
#   - 22 個容器：16 業務 + 3 基礎設施 + 3 運維輔助
#   - 業務容器分 5 層 + 1 獨立（backtest）
#   - 網路：ccurr-net（內部）+ macvlan-net（對外，RouterOS 分流）
#   - 資料庫：Redis + MariaDB + ClickHouse
#   - 唯一出口：ccurr-trader（走 Tailscale exit node）
#   - K 線容器：透過 RouterOS 依 IP 分流到 3 條寬頻
# ============================================================

version: "3.9"

# ============================================================
# 日誌錨點（所有容器共用）
# ============================================================
x-default-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

# ============================================================
# Networks
# ============================================================
networks:
  # 內部通訊（UDS 共享 volume + 服務發現）
  ccurr-net:
    driver: bridge
    name: ccurr-net

  # 對外網路（RouterOS 依 IP 分流到 3 條寬頻）
  # ⚠️ parent 必須改成你實體機的網卡名稱（用 `ip a` 確認）
  macvlan-net:
    driver: macvlan
    name: macvlan-net
    driver_opts:
      parent: enP4p65s0
    ipam:
      config:
        - subnet: 192.168.200.0/23
          gateway: 192.168.200.1

# ============================================================
# Volumes
# ============================================================
volumes:
  # UDS socket 共享（所有使用 UDS 的容器都掛載）
  ccurr-sockets:
    driver: local

  # Redis 資料（持久化）
  ccurr-redis-data:
    driver: local

  # MariaDB 資料（持久化）
  ccurr-mariadb-data:
    driver: local

  # ClickHouse 資料（持久化）
  ccurr-clickhouse-data:
    driver: local

  # 本地 fallback（dbwriter 掛掉時寫入）
  ccurr-fallback:
    driver: local

  # Uptime Kuma 資料（持久化）
  ccurr-uptime-kuma-data:
    driver: local

  # Redis Insight 資料（持久化）
  ccurr-redis-insight-data:
    driver: local

# ============================================================
# Services
# ============================================================
services:

  # ==========================================================
  # 第 1 層：基礎設施
  # ==========================================================

  ccurr-redis:
    image: redis:7-alpine
    container_name: ccurr-redis
    restart: unless-stopped
    init: true
    networks:
      - ccurr-net
    volumes:
      - ccurr-redis-data:/data
    command: >
      redis-server
      --appendonly yes
      --save 60 1
    logging: *default-logging
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  ccurr-mariadb:
    image: mariadb:11
    container_name: ccurr-mariadb
    restart: unless-stopped
    init: true
    networks:
      - ccurr-net
    environment:
      - TZ=Asia/Hong_Kong
      - MARIADB_ROOT_PASSWORD=${MARIADB_ROOT_PASSWORD}
      - MARIADB_DATABASE=ccurr
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
    volumes:
      - ccurr-mariadb-data:/var/lib/mysql
      - ./init/mariadb:/docker-entrypoint-initdb.d:ro
    logging: *default-logging
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 3

  ccurr-clickhouse:
    image: clickhouse/clickhouse-server:24
    container_name: ccurr-clickhouse
    restart: unless-stopped
    init: true
    networks:
      - ccurr-net
    environment:
      - TZ=Asia/Hong_Kong
      - CLICKHOUSE_DB=ccurr
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
    volumes:
      - ccurr-clickhouse-data:/var/lib/clickhouse
      - ./init/clickhouse:/docker-entrypoint-initdb.d:ro
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
    logging: *default-logging
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8123/ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # ==========================================================
  # 第 2 層：核心服務
  # ==========================================================

  # ----------------------------------------------------------
  # ccurr-trader：幣安唯一出口
  # ----------------------------------------------------------
  # 特性：
  #   - 使用自訂 image（已預裝 Tailscale）
  #   - 走 RouterOS 預設路由 → Tailscale exit node → AWS VPS
  #   - 不做分流（mangle 規則第 0、2 條放行）
  #   - 需要 NET_ADMIN + NET_RAW + /dev/net/tun（Tailscale）
  #   - 不使用 privileged（已改為 cap_add）
  # ----------------------------------------------------------
  ccurr-trader:
    build:
      context: .
      dockerfile: ccurr-trader/Dockerfile
    # 若使用自訂 image，註解上方 build 並使用下方：
    # image: ccurr-trader:latest
    # pull_policy: never
    container_name: ccurr-trader
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      # Tailscale
      - TS_AUTHKEY=${TS_AUTHKEY}
      - TS_EXIT_NODE=${TS_EXIT_NODE}
      - TS_ALLOW_LAN=true
      # Binance
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_API_SECRET=${BINANCE_API_SECRET}
      - BINANCE_BASE_URL=https://api.binance.com
      # Redis
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      # UDS
      - UDS_PATH=/sockets/trader.sock
      # Logging
      - LOG_LEVEL=INFO
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.120
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
    volumes:
      # 程式碼（開發模式掛載，生產環境建議打包進 image）
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      # Tailscale 狀態（持久化，避免每次重啟重新認證）
      - /vol2/1000/d2-docker/ccurr/tailscale:/var/lib/tailscale
      # 啟動腳本
      - /vol2/1000/d2-docker/ccurr/ccurr-trader/start_trader.sh:/start_trader.sh:ro
      # UDS socket 共享
      - ccurr-sockets:/sockets
      # 本地 fallback
      - ccurr-fallback:/data/fallback
    cap_add:
      - NET_ADMIN
      - NET_RAW
    devices:
      - /dev/net/tun:/dev/net/tun
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 512M
    depends_on:
      ccurr-redis:
        condition: service_healthy
    working_dir: /app
    command: ["/start_trader.sh"]

  # ----------------------------------------------------------
  # ccurr-dbwriter：所有 DB 寫入統一入口
  # ----------------------------------------------------------
  # 特性：
  #   - 只走 ccurr-net（不需對外）
  #   - 同時負責 ClickHouse（async）與 MariaDB（sync/async）
  #   - 批次聚合：累積 1000 筆或 5 秒觸發
  #   - 背壓保護：佇列滿回 QUEUE_FULL
  # ----------------------------------------------------------
  ccurr-dbwriter:
    build:
      context: .
      dockerfile: ccurr-dbwriter/Dockerfile
    container_name: ccurr-dbwriter
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      # Redis
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      # MariaDB
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_PORT=3306
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      # ClickHouse
      - CLICKHOUSE_HOST=ccurr-clickhouse
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - CLICKHOUSE_DATABASE=ccurr
      # UDS
      - UDS_PATH=/sockets/dbwriter.sock
      # 批次設定
      - ASYNC_BATCH_SIZE=1000
      - ASYNC_FLUSH_SEC=5
      - QUEUE_MAX_SIZE=50000
      - RETRY_MAX=3
      # Logging
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 512M
    depends_on:
      ccurr-redis:
        condition: service_healthy
      ccurr-mariadb:
        condition: service_healthy
      ccurr-clickhouse:
        condition: service_healthy
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ==========================================================
  # 第 3 層：資料服務
  # ==========================================================

  # ----------------------------------------------------------
  # ccurr-accountsync：帳戶快照 + Symbol 同步 + BNB Keeper
  # ----------------------------------------------------------
  ccurr-accountsync:
    build:
      context: .
      dockerfile: ccurr-accountsync/Dockerfile
    container_name: ccurr-accountsync
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - TRADER_UDS_PATH=/sockets/trader.sock
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - SYNC_INTERVAL_SEC=15
      - PRICE_REFRESH_SEC=5
      - SYMBOL_SYNC_INTERVAL_SEC=3600
      - BNB_CHECK_INTERVAL_SEC=60
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      - ccurr-trader
      - ccurr-dbwriter
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-websocket：實時行情監控（WebSocket + OrderBook）
  # ----------------------------------------------------------
  ccurr-websocket:
    build:
      context: .
      dockerfile: ccurr-websocket/Dockerfile
    container_name: ccurr-websocket
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - BINANCE_WS_URL=wss://stream.binance.com:9443/stream
      - BINANCE_REST_URL=https://api.binance.com
      - TOP_N_VOLUME=30
      - TOP_N_ORDERBOOK=5
      - TOP_N_AGGTRADE=3
      - VOLUME_REFRESH_SEC=60
      - SUBSCRIPTION_RECONCILE_SEC=60
      - ENABLE_ORDERBOOK=true
      - ENABLE_AGGTRADE=false
      - OBI_DEPTH=20
      - BIG_TRADE_MULTIPLIER=20.0
      - MIN_TOTAL_DEPTH_USDT=100000
      - MAX_SPREAD_PCT=0.2
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 512M
    depends_on:
      - ccurr-accountsync
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-k5m：5 分鐘 K 線採集 + 指標
  # ----------------------------------------------------------
  # 網路：macvlan IP 192.168.201.121
  # RouterOS 分流：PCC 均分 3 條寬頻（mangle 規則 12-17）
  # 排程：每 5 分鐘（COLLECTOR_INTERVAL=300）
  # ----------------------------------------------------------
  ccurr-k5m:
    build:
      context: .
      dockerfile: ccurr-k5m/Dockerfile
    container_name: ccurr-k5m
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - SERVICE_NAME=ccurr-k5m
      - TIMEFRAME=5m
      - COLLECTOR_INTERVAL=300
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - CLICKHOUSE_HOST=ccurr-clickhouse
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - CLICKHOUSE_DATABASE=ccurr
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - LOG_LEVEL=INFO
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.121
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      ccurr-dbwriter:
        condition: service_started
      ccurr-accountsync:
        condition: service_started
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-k1h：1 小時 K 線採集
  # ----------------------------------------------------------
  # 網路：macvlan IP 192.168.201.122
  # RouterOS 分流：強制走 PCCW1（mangle 規則 9）
  # 排程：每 1 小時（COLLECTOR_INTERVAL=3600）
  # ----------------------------------------------------------
  ccurr-k1h:
    build:
      context: .
      dockerfile: ccurr-k1h/Dockerfile
    container_name: ccurr-k1h
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - SERVICE_NAME=ccurr-k1h
      - TIMEFRAME=1h
      - COLLECTOR_INTERVAL=3600
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - CLICKHOUSE_HOST=ccurr-clickhouse
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - CLICKHOUSE_DATABASE=ccurr
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - LOG_LEVEL=INFO
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.122
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      ccurr-dbwriter:
        condition: service_started
      ccurr-accountsync:
        condition: service_started
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-k4h：4 小時 K 線採集
  # ----------------------------------------------------------
  # 網路：macvlan IP 192.168.201.123
  # RouterOS 分流：強制走 PCCW2（mangle 規則 10）
  # 排程：每 1 小時（COLLECTOR_INTERVAL=3600）
  # ⚠️ 注意：原本 4 小時，改為 1 小時讓未完成的 4h K 線可被 Step 2 掃描
  # ----------------------------------------------------------
  ccurr-k4h:
    build:
      context: .
      dockerfile: ccurr-k4h/Dockerfile
    container_name: ccurr-k4h
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - SERVICE_NAME=ccurr-k4h
      - TIMEFRAME=4h
      - COLLECTOR_INTERVAL=3600
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - CLICKHOUSE_HOST=ccurr-clickhouse
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - CLICKHOUSE_DATABASE=ccurr
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - LOG_LEVEL=INFO
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.123
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      ccurr-dbwriter:
        condition: service_started
      ccurr-accountsync:
        condition: service_started
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-k1d：1 日 K 線採集
  # ----------------------------------------------------------
  # 網路：macvlan IP 192.168.201.124
  # RouterOS 分流：強制走 CMHK1（mangle 規則 11）
  # 排程：每 1 小時（COLLECTOR_INTERVAL=3600）
  # ⚠️ 注意：原本 24 小時，改為 1 小時讓未完成的 1d K 線可被 Step 2 掃描
  # ----------------------------------------------------------
  ccurr-k1d:
    build:
      context: .
      dockerfile: ccurr-k1d/Dockerfile
    container_name: ccurr-k1d
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - SERVICE_NAME=ccurr-k1d
      - TIMEFRAME=1d
      - COLLECTOR_INTERVAL=3600
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - CLICKHOUSE_HOST=ccurr-clickhouse
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - CLICKHOUSE_DATABASE=ccurr
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - LOG_LEVEL=INFO
    networks:
      macvlan-net:
        ipv4_address: 192.168.201.124
        priority: 1000
        gw_priority: 1
      ccurr-net:
        priority: 100
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      ccurr-dbwriter:
        condition: service_started
      ccurr-accountsync:
        condition: service_started
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ==========================================================
  # 第 4 層：決策與執行
  # ==========================================================

  # ----------------------------------------------------------
  # ccurr-risk：風控守門員（只讀 Redis）
  # ----------------------------------------------------------
  ccurr-risk:
    build:
      context: .
      dockerfile: ccurr-risk/Dockerfile
    container_name: ccurr-risk
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - UDS_PATH=/sockets/risk.sock
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      - ccurr-accountsync
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-executor：信號執行（三通道）
  # ----------------------------------------------------------
  ccurr-executor:
    build:
      context: .
      dockerfile: ccurr-executor/Dockerfile
    container_name: ccurr-executor
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - TRADER_UDS_PATH=/sockets/trader.sock
      - RISK_UDS_PATH=/sockets/risk.sock
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - NORMAL_QUEUE_MAX=1000
      - EMERGENCY_QUEUE_MAX=100
      - LOCK_TTL_SEC=10
      - LOCK_WAIT_SEC=3.0
      - TRADER_RETRY_MAX=3
      - MAINTENANCE_STRATEGY_IDS=bnb_keeper
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      - ccurr-trader
      - ccurr-risk
      - ccurr-dbwriter
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-order：訂單追蹤（含寫穿 + 超時管理）
  # ----------------------------------------------------------
  ccurr-order:
    build:
      context: .
      dockerfile: ccurr-order/Dockerfile
    container_name: ccurr-order
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - TRADER_UDS_PATH=/sockets/trader.sock
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - SYNC_INTERVAL_SEC=10
      - UNKNOWN_CHECK_INTERVAL_SEC=30
      - TIMEOUT_CHECK_INTERVAL_SEC=60
      - POSITION_WRITETHROUGH_TTL_SEC=60
      - CANCEL_RETRY_MAX=3
      - CANCEL_RETRY_BACKOFF_SEC=2.0
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      - ccurr-trader
      - ccurr-dbwriter
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-override：多階段緊急平倉
  # ----------------------------------------------------------
  ccurr-override:
    build:
      context: .
      dockerfile: ccurr-override/Dockerfile
    container_name: ccurr-override
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - UDS_PATH=/sockets/override.sock
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - OVERRIDE_ENABLED=true
      - DEFAULT_CLOSE_PCT=50
      - DEFAULT_OBSERVE_MIN=15
      - DEFAULT_DROP_THRESHOLD_PCT=3.0
      - DEFAULT_RISE_THRESHOLD_PCT=3.0
      - DEFAULT_SECOND_CLOSE_PCT=25
      - DEFAULT_MAX_STAGES=3
      - PRICE_CHECK_INTERVAL_SEC=60
      - LOCK_OVERRIDE_TTL_SEC=30
      - LOCK_CONFIG_TTL_SEC=10
      - STATE_TTL_SEC=604800
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      - ccurr-executor
      - ccurr-accountsync
      - ccurr-dbwriter
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-strategy：策略引擎
  # ----------------------------------------------------------
  ccurr-strategy:
    build:
      context: .
      dockerfile: ccurr-strategy/Dockerfile
    container_name: ccurr-strategy
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - UDS_PATH=/sockets/strategy.sock
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - CLICKHOUSE_HOST=ccurr-clickhouse
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - CLICKHOUSE_DATABASE=ccurr
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - PLUGINS_DIR=/app/plugins
      - SCAN_INTERVAL_SEC=900
      - SCAN_TIMEOUT_SEC=60
      - REVIEW_POLL_INTERVAL_SEC=30
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 512M
    depends_on:
      - ccurr-dbwriter
      - ccurr-accountsync
      - ccurr-k5m
      - ccurr-k1h
      - ccurr-k4h
      - ccurr-k1d
      - ccurr-websocket
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ==========================================================
  # 第 5 層：介面與監控
  # ==========================================================

  # ----------------------------------------------------------
  # ccurr-telegram：人機介面
  # ----------------------------------------------------------
  ccurr-telegram:
    build:
      context: .
      dockerfile: ccurr-telegram/Dockerfile
    container_name: ccurr-telegram
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_OWNER_ID=${TELEGRAM_OWNER_ID}
      - ALERT_CHANNEL=alert:all
      - POLLING_TIMEOUT_SEC=30
      - RATE_LIMIT_PER_MIN=30
      - CONFIRM_TIMEOUT_SEC=120
      - MEDIUM_ALERT_BATCH_SEC=300
      - MAX_MESSAGE_LEN=4000
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      - ccurr-strategy
      - ccurr-override
      - ccurr-risk
      - ccurr-trader
      - ccurr-monitor
      - ccurr-dbwriter
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ----------------------------------------------------------
  # ccurr-monitor：監控告警 + 降級維護
  # ----------------------------------------------------------
  ccurr-monitor:
    build:
      context: .
      dockerfile: ccurr-monitor/Dockerfile
    container_name: ccurr-monitor
    restart: unless-stopped
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=ccurr-redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - UDS_PATH=/sockets/monitor.sock
      - DBWRITER_UDS_PATH=/sockets/dbwriter.sock
      - DOCKER_ENABLED=false
      - SCAN_INTERVAL_SEC=30
      - DEGRADATION_UPDATE_SEC=30
      - DEDUP_CRITICAL_SEC=60
      - DEDUP_HIGH_SEC=300
      - DEDUP_MEDIUM_SEC=900
      - DEDUP_LOW_SEC=3600
      - RESTART_ALLOWED_CONTAINERS=""
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ccurr-sockets:/sockets
      - ccurr-fallback:/data/fallback
      # 若啟用 Docker 重啟功能才掛載
      # - /var/run/docker.sock:/var/run/docker.sock:ro
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M
    depends_on:
      - ccurr-dbwriter
    working_dir: /app
    command: ["python", "-m", "app.main"]

  # ==========================================================
  # 獨立：回測引擎（不參與實盤）
  # ==========================================================

  ccurr-backtest:
    build:
      context: .
      dockerfile: ccurr-backtest/Dockerfile
    container_name: ccurr-backtest
    restart: "no"
    init: true
    environment:
      - TZ=Asia/Hong_Kong
      - PYTHONUNBUFFERED=1
      - CLICKHOUSE_HOST=ccurr-clickhouse
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - CLICKHOUSE_DATABASE=ccurr
      - MARIADB_HOST=ccurr-mariadb
      - MARIADB_USER=ccurr
      - MARIADB_PASSWORD=${MARIADB_PASSWORD}
      - MARIADB_DB=ccurr
      - PLUGINS_DIR=/app/plugins
      - DEFAULT_FEE_PCT=0.1
      - DEFAULT_SLIPPAGE_PCT=0.05
      - DEFAULT_STEP_MS=300000
      - LOG_LEVEL=INFO
    networks:
      - ccurr-net
    volumes:
      - /vol2/1000/d2-docker/ccurr/cc-py:/app
      - ./backtest-results:/app/results
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 2G
    depends_on:
      - ccurr-clickhouse
      - ccurr-mariadb
    working_dir: /app
    command: ["python", "-m", "app.main"]
    profiles:
      - backtest   # 用 `docker compose --profile backtest up` 才啟動

  # ==========================================================
  # 運維輔助容器（不屬於 16 個業務容器）
  # ==========================================================

  # ----------------------------------------------------------
  # ccurr-dozzle：容器日誌即時查看（Web UI）
  # ----------------------------------------------------------
  # 特性：
  #   - 只讀 docker.sock（:ro），不能操作容器
  #   - 停用 web shell 與容器操作按鈕
  #   - 只顯示 name=ccurr- 開頭的容器
  #   - 詳見 6.18 節
  # ----------------------------------------------------------
  ccurr-dozzle:
    image: amir20/dozzle:latest
    container_name: ccurr-dozzle
    restart: unless-stopped
    init: true
    networks:
      - ccurr-net
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - TZ=Asia/Hong_Kong
      - DOZZLE_LEVEL=info
      - DOZZLE_TAILSIZE=300
      - DOZZLE_FILTER=name=ccurr-
      - DOZZLE_ENABLE_ACTIONS=false
      - DOZZLE_ENABLE_SHELL=false
    ports:
      # 綁定 CM3588 內網 IP（開發機可直接訪問）
      # 若需更安全，改為 "127.0.0.1:9999:8080" + SSH tunnel
      - "192.168.200.121:9999:8080"
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 128M

  # ----------------------------------------------------------
  # ccurr-uptime-kuma：服務健康監控（Web UI）
  # ----------------------------------------------------------
  # 特性：
  #   - 監控有 TCP port 的服務（redis / mariadb / clickhouse）
  #   - UDS 服務的監控見 6.18.2 說明
  #   - 詳見 6.18.2 節
  # ----------------------------------------------------------
  ccurr-uptime-kuma:
    image: louislam/uptime-kuma:1
    container_name: ccurr-uptime-kuma
    restart: unless-stopped
    init: true
    networks:
      - ccurr-net
    volumes:
      - ccurr-uptime-kuma-data:/app/data
    environment:
      - TZ=Asia/Hong_Kong
    ports:
      - "192.168.200.121:3001:3001"
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M

  # ----------------------------------------------------------
  # ccurr-redis-insight：Redis 視覺化（Web UI）
  # ----------------------------------------------------------
  # 特性：
  #   - 首次訪問需手動輸入 Redis 連線資訊
  #   - 不預設連接生產 Redis
  #   - 詳見 6.18.3 節
  # ----------------------------------------------------------
  ccurr-redis-insight:
    image: redis/redisinsight:latest
    container_name: ccurr-redis-insight
    restart: unless-stopped
    init: true
    networks:
      - ccurr-net
    volumes:
      - ccurr-redis-insight-data:/data
    environment:
      - TZ=Asia/Hong_Kong
      - RI_APP_PORT=5540
    ports:
      - "192.168.200.121:5540:5540"
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256M


```

### 6.15.3 環境變數檔（.env）

```bash

# ============================================================
# ccurr 環境變數範本
# ============================================================
# 使用方式：
#   cp .env.example .env
#   編輯 .env 填入真實值
# ============================================================

# ============================================================
# 資料庫密碼
# ============================================================
MARIADB_ROOT_PASSWORD=changeme_root_password
MARIADB_PASSWORD=changeme_ccurr_password
CLICKHOUSE_PASSWORD=changeme_clickhouse_password
REDIS_PASSWORD=

# ============================================================
# 幣安 API
# ============================================================
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
# 注意：舊版用 BINANCE_SECRET_KEY，新版統一為 BINANCE_API_SECRET

# ============================================================
# Tailscale（ccurr-trader 專用）
# ============================================================
# 從 https://login.tailscale.com/admin/settings/keys 取得
TS_AUTHKEY=tskey-auth-xxxxxxxxxxxxx
# AWS VPS 的 Tailscale IP（exit node）
TS_EXIT_NODE=100.x.x.x

# ============================================================
# Telegram
# ============================================================
# 從 @BotFather 取得
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
# 從 @userinfobot 取得你的 Telegram User ID
TELEGRAM_OWNER_ID=123456789
```

### 6.15.4 網路架構

| 網路            | 用途                       | 綁定容器                       |
| --------------- | -------------------------- | ------------------------------ |
| `ccurr-net`   | 內部通訊（UDS + 服務發現） | 全部（含運維容器）             |
| `macvlan-net` | 對外通訊（RouterOS 分流）  | `ccurr-trader`、`ccurr-k*` |

**只有需要對外的容器才綁 macvlan**：

* `ccurr-trader`：走 Tailscale exit node
* `ccurr-k5m/k1h/k4h/k1d`：走 RouterOS 分流
* 其他容器（dbwriter、risk、executor 等）：只需 `ccurr-net`
* 運維容器（Dozzle / Uptime Kuma / Redis Insight）：只綁 `ccurr-net` + 對內網開放 port

### 6.15.5 K 線容器 IP 分配

| 容器             | IP                  | RouterOS 分流         |
| ---------------- | ------------------- | --------------------- |
| `ccurr-trader` | `192.168.201.120` | 預設路由 → Tailscale |
| `ccurr-k5m`    | `192.168.201.121` | PCC 均分 3 條寬頻     |
| `ccurr-k1h`    | `192.168.201.122` | 強制 PCCW1            |
| `ccurr-k4h`    | `192.168.201.123` | 強制 PCCW2            |
| `ccurr-k1d`    | `192.168.201.124` | 強制 CMHK1            |

### 6.15.6 記憶體限制

| 容器                    | 限制 | 說明                   |
| ----------------------- | ---- | ---------------------- |
| `ccurr-trader`        | 512M | Tailscale + 幣安客戶端 |
| `ccurr-dbwriter`      | 512M | 批次聚合               |
| `ccurr-websocket`     | 512M | OrderBook 快取         |
| `ccurr-strategy`      | 512M | 策略引擎               |
| `ccurr-k*`            | 256M | K 線採集               |
| `ccurr-accountsync`   | 256M | 帳戶同步               |
| 其他                    | 256M | 一般容器               |
| `ccurr-backtest`      | 2G   | 回測吃記憶體           |
| `ccurr-dozzle`        | 128M | 容器日誌查看           |
| `ccurr-uptime-kuma`   | 256M | 服務健康監控           |
| `ccurr-redis-insight` | 256M | Redis 視覺化           |

### 6.15.7 部署指令

```bash
# 1. 建立 .env
cp .env.example .env
vim .env

# 2. 建立目錄
mkdir -p init/mariadb init/clickhouse
mkdir -p /vol2/1000/d2-docker/ccurr/cc-py
mkdir -p /vol2/1000/d2-docker/ccurr/tailscale
mkdir -p /vol2/1000/d2-docker/ccurr/ccurr-trader

# 3. 啟動基礎設施
docker compose up -d ccurr-redis ccurr-mariadb ccurr-clickhouse

# 4. 等待健康檢查
docker compose ps

# 5. 啟動核心服務
docker compose up -d ccurr-trader ccurr-dbwriter

# 6. 啟動資料服務
docker compose up -d ccurr-accountsync ccurr-websocket
docker compose up -d ccurr-k5m ccurr-k1h ccurr-k4h ccurr-k1d

# 7. 啟動決策與執行
docker compose up -d ccurr-risk ccurr-executor ccurr-order ccurr-override ccurr-strategy

# 8. 啟動介面與監控
docker compose up -d ccurr-telegram ccurr-monitor

# 9. 全部啟動
docker compose up -d

# 10. 查看日誌
docker compose logs -f ccurr-trader
docker compose logs -f ccurr-k5m

# 11. 停止
docker compose down

# 12. 回測（用 profile）
docker compose --profile backtest up ccurr-backtest
```

## 6.16 依賴矩陣

### 6.16.1 啟動依賴

| 容器                    | 依賴容器                                                                                                        | 條件    |
| ----------------------- | --------------------------------------------------------------------------------------------------------------- | ------- |
| `ccurr-redis`         | —                                                                                                              | —      |
| `ccurr-mariadb`       | —                                                                                                              | —      |
| `ccurr-clickhouse`    | —                                                                                                              | —      |
| `ccurr-trader`        | `ccurr-redis`                                                                                                 | healthy |
| `ccurr-dbwriter`      | `ccurr-redis`、`ccurr-mariadb`、`ccurr-clickhouse`                                                        | healthy |
| `ccurr-accountsync`   | `ccurr-trader`、`ccurr-dbwriter`                                                                            | started |
| `ccurr-websocket`     | `ccurr-accountsync`                                                                                           | started |
| `ccurr-k5m`           | `ccurr-dbwriter`、`ccurr-accountsync`                                                                       | started |
| `ccurr-k1h`           | `ccurr-dbwriter`、`ccurr-accountsync`                                                                       | started |
| `ccurr-k4h`           | `ccurr-dbwriter`、`ccurr-accountsync`                                                                       | started |
| `ccurr-k1d`           | `ccurr-dbwriter`、`ccurr-accountsync`                                                                       | started |
| `ccurr-risk`          | `ccurr-accountsync`                                                                                           | started |
| `ccurr-executor`      | `ccurr-trader`、`ccurr-risk`、`ccurr-dbwriter`                                                            | started |
| `ccurr-order`         | `ccurr-trader`、`ccurr-dbwriter`                                                                            | started |
| `ccurr-override`      | `ccurr-executor`、`ccurr-accountsync`、`ccurr-dbwriter`                                                   | started |
| `ccurr-strategy`      | `ccurr-dbwriter`、`ccurr-accountsync`、`ccurr-k*`、`ccurr-websocket`                                    | started |
| `ccurr-telegram`      | `ccurr-strategy`、`ccurr-override`、`ccurr-risk`、`ccurr-trader`、`ccurr-monitor`、`ccurr-dbwriter` | started |
| `ccurr-monitor`       | `ccurr-dbwriter`                                                                                              | started |
| `ccurr-backtest`      | `ccurr-clickhouse`、`ccurr-mariadb`                                                                         | started |
| `ccurr-dozzle`        | —                                                                                                              | —      |
| `ccurr-uptime-kuma`   | —                                                                                                              | —      |
| `ccurr-redis-insight` | —                                                                                                              | —      |

### 6.16.2 `shared/` 模組依賴

| 容器                  | trace | locks | event_bus | audit | degradation | dynamic_config | strategy_log | uds_client |
| --------------------- | ----- | ----- | --------- | ----- | ----------- | -------------- | ------------ | ---------- |
| `ccurr-trader`      | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | —         |
| `ccurr-dbwriter`    | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | —         |
| `ccurr-accountsync` | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | ✅         |
| `ccurr-websocket`   | ✅    | ✅    | ✅        | —    | ✅          | ✅             | —           | —         |
| `ccurr-k*`          | ✅    | ✅    | ✅        | —    | ✅          | ✅             | —           | ✅         |
| `ccurr-risk`        | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | —         |
| `ccurr-executor`    | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | ✅         |
| `ccurr-order`       | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | ✅         |
| `ccurr-override`    | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | ✅         |
| `ccurr-strategy`    | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | ✅           | ✅         |
| `ccurr-telegram`    | ✅    | ✅    | ✅        | ✅    | ✅          | ✅             | —           | ✅         |
| `ccurr-monitor`     | ✅    | —    | ✅        | ✅    | ✅          | ✅             | —           | ✅         |
| `ccurr-backtest`    | —    | —    | —        | —    | —          | —             | —           | —         |

 **注意** ：`ccurr-backtest` 不依賴任何 `shared/` 模組（除 `time_utils`、`models`）。

### 6.16.3 Redis 依賴

| 容器                  | 讀                                                                                        | 寫                                                                                                  | Pub/Sub 訂閱                                | Pub/Sub 發布                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `ccurr-trader`      | `trader:*`                                                                              | `trader:*`、`heartbeat:*`                                                                       | —                                          | —                                                                                                                           |
| `ccurr-dbwriter`    | —                                                                                        | `stats:*`                                                                                         | —                                          | —                                                                                                                           |
| `ccurr-accountsync` | `position:*`、`blacklist:cache`                                                       | `account:*`、`balance:*`、`position:*`                                                        | —                                          | `signal:all`、`account.synced`、`alert:all`                                                                            |
| `ccurr-websocket`   | `position:*`、`blacklist:cache`、`ws:config`                                        | `ws:*`                                                                                            | —                                          | `ws:*`、`alert:all`                                                                                                      |
| `ccurr-k*`          | —                                                                                        | `heartbeat:*`、`stats:*`                                                                        | —                                          | —                                                                                                                           |
| `ccurr-risk`        | `account:*`、`position:*`、`balance:*`、`price:*`、`risk:*`、`ws:liquidity:*` | `risk:*`、`heartbeat:*`、`stats:*`                                                            | `position:updated`、`override:executed` | `alert:all`                                                                                                                |
| `ccurr-executor`    | `order:pending:*`、`signal:*`                                                         | `order:pending:*`、`order:timeout_queue`、`order:pending_oco:*`、`heartbeat:*`、`stats:*` | `signal:all`、`signal:emergency`        | `order:placed`、`alert:all`                                                                                              |
| `ccurr-order`       | `order:pending:*`、`order:timeout_queue`、`order:pending_oco:*`、`position:*`     | `position:*`、`order:pending:*`、`heartbeat:*`、`stats:*`                                   | —                                          | `position:updated`、`order:filled`、`order:cancelled`、`order:timeout_canceled`、`order:oco_placed`、`alert:all` |
| `ccurr-override`    | `position:*`、`price:*`、`override:*`                                               | `override:*`、`heartbeat:*`、`stats:*`                                                        | —                                          | `signal:emergency`、`alert:all`                                                                                          |
| `ccurr-strategy`    | `position:*`、`strategy:*`、`config:*`                                              | `strategy:*`、`heartbeat:*`、`stats:*`                                                        | `config:changed`                          | `signal:all`、`telegram:send`、`alert:all`                                                                             |
| `ccurr-telegram`    | `telegram:*`、`alert:*`                                                               | `telegram:*`、`heartbeat:*`、`stats:*`                                                        | `alert:all`、`telegram:send`            | `config:changed`                                                                                                           |
| `ccurr-monitor`     | `heartbeat:*`、`stats:*`、`system:degradation`                                      | `system:degradation`、`alert:dedup:*`、`monitor:history`、`heartbeat:*`、`stats:*`        | —                                          | `system:degradation`、`alert:all`                                                                                        |

---

## 6.17 部署檢查清單

### 6.17.1 部署前檢查

```text
【基礎設施】
□ Docker 已安裝（版本 ≥ 24）
□ Docker Compose 已安裝（版本 ≥ 2.20）
□ 宿主機網路已設定 3 條寬頻（eth1 / eth2 / eth3）
□ MikroTik RB5009 已設定 macvlan 對應
□ Tailscale 已安裝並設定 exit node
□ AWS VPS 已設定固定 IP 並允許 Tailscale 流量

【環境變數】
□ .env 檔案已建立
□ BINANCE_API_KEY / SECRET 已填寫
□ TELEGRAM_BOT_TOKEN / OWNER_ID 已填寫
□ MARIADB / CLICKHOUSE 密碼已設定

【資料庫初始化】
□ MariaDB init SQL 已放入 ./init/mariadb/
□ ClickHouse init SQL 已放入 ./init/clickhouse/
□ 所有資料表 Schema 已建立

【Socket 共享】
□ ccurr-sockets volume 已建立
□ 所有使用 UDS 的容器都掛載此 volume

【幣安 API】
□ API Key 已啟用現貨交易
□ API Key 已允許固定 IP（AWS VPS）
□ API Key 權限：現貨交易、查帳戶
□ 已關閉提幣權限（安全）
```

### 6.17.2 部署後驗證

```text
【基礎設施】
□ ccurr-redis 健康
□ ccurr-mariadb 健康
□ ccurr-clickhouse 健康

【核心服務】
□ ccurr-trader 健康（查 /health）
□ ccurr-dbwriter 健康（查 /health）

【資料服務】
□ ccurr-accountsync 已同步帳戶
□ ccurr-websocket 已訂閱（查 stats）
□ ccurr-k5m 已回補 K 線（查 ClickHouse）
□ ccurr-k1h / k4h / k1d 同上

【決策與執行】
□ ccurr-risk 健康
□ ccurr-executor 健康
□ ccurr-order 健康
□ ccurr-override 健康
□ ccurr-strategy 已載入策略

【介面與監控】
□ ccurr-telegram 已連接
□ ccurr-monitor 已運作

【功能驗證】
□ Telegram /status 有回應
□ Telegram /balance 顯示正確餘額
□ Telegram /health 顯示所有容器狀態
□ Telegram /degradation 顯示所有容器 ok
□ 手動觸發策略掃描（/strategy/reload）
□ 檢查 strategy_run_log 有記錄
```

### 6.17.3 安全檢查

```text
【API 安全】
□ 幣安 API Key 只允許固定 IP
□ 幣安 API Key 關閉提幣權限
□ Telegram Bot 只允許私訊
□ Telegram 白名單已設定

【資料庫安全】
□ MariaDB root 密碼強度足夠
□ ClickHouse 密碼已設定
□ Redis 不暴露到公網
□ 所有資料庫只在 internal network

【Docker 安全】
□ 不使用 privileged 模式
□ 只在需要時掛載 docker.sock
□ 所有容器使用非 root 使用者（可選）

【網路安全】
□ Tailscale exit node 已加密
□ AWS VPS 防火牆已設定
□ 所有 UDS socket 只在內部共享
```

---

## 6.18 運維輔助容器

> 本節涵蓋**非業務容器**——只為開發 / 維運而存在，不參與交易邏輯。
> **業務容器數量維持 16 個不變**；本節容器另計。

### 6.18.1 `ccurr-dozzle`

#### 職責

**容器日誌即時查看**（Web UI）。提供所有 `ccurr-*` 容器的 log 即時瀏覽、搜尋、過濾。

#### 對外介面

| 方向 | 介面          | 說明                                        |
| ---- | ------------- | ------------------------------------------- |
| 入   | HTTP          | `http://192.168.200.121:9999`（僅綁內網） |
| 入   | Docker socket | `/var/run/docker.sock`（唯讀）            |

#### 核心功能點

1. **即時日誌**（WebSocket 推送）
2. **多容器同看**（Grid 版面）
3. **搜尋 / 過濾**（regex 支援）
4. **下載日誌**（單容器）
5. **容器過濾**（只顯示 `name=ccurr-`）

#### 關鍵約束

* **不屬於 16 個業務容器**
* 只讀 `docker.sock`（`:ro`），**不能操作容器**
* 停用 web shell（`DOZZLE_ENABLE_SHELL=false`）
* 停用容器操作按鈕（`DOZZLE_ENABLE_ACTIONS=false`）
* 只顯示 `name=ccurr-` 開頭的容器（`DOZZLE_FILTER`）
* 資源限制 128M
* 無認證機制，**只綁內網 IP**（不放公網）

#### 環境變數

| 變數                      | 說明             | 預設             |
| ------------------------- | ---------------- | ---------------- |
| `SERVICE_NAME`          | 服務名稱         | `ccurr-dozzle` |
| `DOZZLE_LEVEL`          | 日誌等級         | `info`         |
| `DOZZLE_TAILSIZE`       | 每個容器顯示行數 | `300`          |
| `DOZZLE_FILTER`         | 容器過濾         | `name=ccurr-`  |
| `DOZZLE_ENABLE_ACTIONS` | 啟用容器操作按鈕 | `false`        |
| `DOZZLE_ENABLE_SHELL`   | 啟用 web shell   | `false`        |
| `DOZZLE_HOSTNAME`       | 顯示的主機名     | （可選）         |

#### 依賴

無（獨立於 16 個業務容器）

#### 資源限制

| 項目   | 限制 |
| ------ | ---- |
| 記憶體 | 128M |

#### 訪問方式

**方式 1：內網直連（已預設）**

```
http://192.168.200.121:9999
```

**方式 2：SSH tunnel（若改綁 127.0.0.1）**

```powershell
# 從開發機執行
ssh -L 9999:localhost:9999 root@192.168.200.121 -N

# 然後瀏覽器開
http://localhost:9999
```

---

### 6.18.2 `ccurr-uptime-kuma`

#### 職責

**服務健康監控**（Web UI）。對所有 `ccurr-*` 容器的心跳 / HTTP 端點做定時探測，異常時推送 Telegram / Email 告警。

**與 ccurr-monitor 的分工**：

- `ccurr-monitor`：內部業務邏輯監控（心跳 Key、佇列深度、熔斷狀態）
- `ccurr-uptime-kuma`：外部服務可達性監控（HTTP ping、TCP port）

兩者互補，**不重疊**。

#### 對外介面

| 方向 | 介面         | 說明                                        |
| ---- | ------------ | ------------------------------------------- |
| 入   | HTTP         | `http://192.168.200.121:3001`（僅綁內網） |
| 出   | HTTP / TCP   | 對 ccurr 容器做探測                         |
| 出   | Telegram API | 告警推送（可選）                            |

#### 核心功能點

1. **HTTP(s) 探測**（對 `/health` 端點）
2. **TCP Port 探測**（對 redis / mariadb / clickhouse）
3. **Heartbeat 被動探測**（若服務主動上報）
4. **狀態頁**（可公開的 Status Page）
5. **告警推送**（Telegram / Email / Webhook）
6. **歷史記錄**（回應時間、可用率）

#### 建議監控項目

| 監控目標             | 方式             | 端點 / Port    |
| -------------------- | ---------------- | -------------- |
| `ccurr-redis`      | TCP              | 6379           |
| `ccurr-mariadb`    | TCP              | 3306           |
| `ccurr-clickhouse` | HTTP             | `:8123/ping` |
| `ccurr-trader`     | HTTP（UDS 代理） | 見下方說明     |
| `ccurr-risk`       | HTTP（UDS 代理） | 同上           |
| `ccurr-monitor`    | HTTP（UDS 代理） | 同上           |
| `ccurr-telegram`   | HTTP（UDS 代理） | 同上           |

**⚠️ UDS 服務的探測方式**：

UDS 服務（trader / risk / monitor / telegram 等）不對外開放 TCP port，Uptime Kuma **無法直接探測**。兩種做法：

- **做法 A（推薦）**：探測 Redis 心跳 Key 的「最後更新時間」
  - 用 Uptime Kuma 的「Push」監控類型
  - 在 `ccurr-monitor` 內加一個小 cron：每 30 秒把心跳讀出並 push 到 Uptime Kuma
- **做法 B（簡化）**：只監控有 TCP port 的服務（redis / mariadb / clickhouse）+ 依靠 ccurr-monitor 的內部心跳監控

**第一版建議用做法 B**，等系統穩定後再考慮做法 A。

#### 關鍵約束

- **不屬於 16 個業務容器**
- 資料持久化（SQLite 內建）
- 資源限制 256M
- 只綁內網 IP（不放公網）
- 告警推送需自行配置（第一版可只做 Web UI）

#### 環境變數

| 變數                                     | 說明             | 預設                  |
| ---------------------------------------- | ---------------- | --------------------- |
| `SERVICE_NAME`                         | 服務名稱         | `ccurr-uptime-kuma` |
| `UPTIME_KUMA_PORT`                     | Web UI 埠        | `3001`              |
| `UPTIME_KUMA_DISABLE_FRAME_SAMEORIGIN` | 允許 iframe 嵌入 | `false`             |

#### 依賴

無（獨立於 16 個業務容器；第一版建議只監控有 TCP port 的服務）

#### 資源限制

| 項目   | 限制 |
| ------ | ---- |
| 記憶體 | 256M |

#### 資料持久化

```text
ccurr-uptime-kuma-data:/app/data
```

（存 SQLite 資料庫 + 監控歷史）

#### 訪問方式

```
http://192.168.200.121:3001
```

首次訪問會引導建立管理員帳號。

---

### 6.18.3 `ccurr-redis-insight`

#### 職責

**Redis 視覺化**（Web UI）。提供 Key 瀏覽、命令列、慢查詢分析、記憶體分析等。

**用途**：

- 開發階段：查看 ccurr 系統寫入的 Key（`position:*`、`order:pending:*`、`strategy:*` 等）
- 除錯階段：手動執行 Redis 命令（`HGETALL`、`XLEN`、`ZRANGEBYSCORE` 等）
- 運維階段：分析記憶體佔用、慢查詢

#### 對外介面

| 方向 | 介面      | 說明                                        |
| ---- | --------- | ------------------------------------------- |
| 入   | HTTP      | `http://192.168.200.121:5540`（僅綁內網） |
| 出   | Redis TCP | `ccurr-redis:6379`                        |

#### 核心功能點

1. **Key 瀏覽**（樹狀 / 列表）
2. **命令列**（Redis CLI in browser）
3. **慢查詢日誌**
4. **記憶體分析**
5. **Pub/Sub 監看**（可看 `signal:all` 等頻道）
6. **多連線管理**（可保存多個 Redis 連線）

#### 關鍵約束

- **不屬於 16 個業務容器**
- **不預設連接生產 Redis**——首次訪問需手動輸入 host / port / password
- 資源限制 256M
- 只綁內網 IP（不放公網）
- **唯讀建議**：開發階段可讀寫，**生產環境建議設定為唯讀**（避免誤刪 Key）

#### 環境變數

| 變數                  | 說明                   | 預設                    |
| --------------------- | ---------------------- | ----------------------- |
| `SERVICE_NAME`      | 服務名稱               | `ccurr-redis-insight` |
| `RI_APP_PORT`       | Web UI 埠              | `5540`                |
| `RI_ENCRYPTION_KEY` | 連線密碼加密用（可選） | —                      |

#### 依賴

- `ccurr-redis`（TCP 連線，但只在 Web UI 內手動建立）

#### 資源限制

| 項目   | 限制 |
| ------ | ---- |
| 記憶體 | 256M |

#### 資料持久化

```text
ccurr-redis-insight-data:/data
```

（存連線設定、UI 偏好）

#### 訪問方式

```
http://192.168.200.121:5540
```

首次進入後，手動新增連線：

- Host：`ccurr-redis`（或 `192.168.200.121`）
- Port：`6379`
- Password：（填入 `REDIS_PASSWORD`）
- Database：`0`

#### 安全建議

**第一版**：

- 可讀寫（開發階段方便）
- 只綁內網 IP

**第二版（實盤後）**：

- 考慮改為唯讀帳號連接（Redis 6+ ACL）
- 或加 nginx basic auth 保護

---

### 6.18.4 擴充方向

未來若需更多運維工具，同屬此類（`6.18.x`）：

| 工具                | 用途                                |
| ------------------- | ----------------------------------- |
| `ccurr-portainer` | 容器管理（已使用中，非 ccurr 專案） |
| `ccurr-grafana`   | 監控儀表板（需 Loki / Prometheus）  |
| `ccurr-loki`      | 日誌聚合（取代 Dozzle 的無持久化）  |

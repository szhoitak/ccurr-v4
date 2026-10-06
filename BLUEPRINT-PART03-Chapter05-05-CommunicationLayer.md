
# 第三部：通訊層

## 5.1 可靠性與資料邊界契約

> Redis Pub/Sub 是 best-effort notification，不具 replay/ACK。事件是否可靠由事件的 authoritative state、dbwriter persistence 與 reconciliation 決定，不得只靠 Pub/Sub 宣稱可靠。

### Lossy / best-effort

`ws:mini_ticker`、`ws:obi`、`ws:big_trade`、`ws:liquidity`、`heartbeat:*`、`stats:*`、`strategy:perf`、async Kline writes 與 low-level alerts 可遺失；採最新值優先、無 ACK/retry，queue full 可拒絕。

### Reliable / state-backed

`signal:all`、`signal:emergency`、`order:placed`、`order:filled`、`position:updated`、`account.synced`、`override:executed`、`config:changed`、`system:degradation` 及 high/critical alerts 必須有持久化狀態、idempotency、retry、replay 或 reconciliation。Pub/Sub 只作快速通知。

### Recovery ownership

- signal：strategy 每 30 秒檢查 approved Candidate 與 `order:pending:*`；60 秒沒有下游訂單時可用相同 idempotency key 重發。
- order：ccurr-order MainLoop 每 10 秒掃描 pending state 接管，不能依賴 `order:placed`。
- position：risk 以 Redis position pull；accountsync 每 15 秒向 Binance 校正。
- high/critical Telegram：失敗寫入 `telegram:buffer:{tg_id}`，由 telegram 重連後補發。

---

## 5.2 DB/Redis/Binance routing matrix

- 私有/交易 Binance REST（order、cancel、OTO/OCO/OTOCO、account、openOrders、allOrders、myTrades、order、orderList）只能經 `ccurr-trader`；API secret 只在 trader。
- public `/api/v3/klines` 由 `ccurr-k*` 直連；public market-data WS 由 `ccurr-websocket` 直連；`exchangeInfo` 可由 accountsync 直連。
- DB 所有 writes 經 `ccurr-dbwriter`；direct SELECT readers 只限 strategy、risk、override、k*、backtest、dbwriter（依 DB/章節 matrix）。
- executor、trader、telegram 不得 direct DB；backtest 僅讀取 offline config/歷史資料，結果先由 backtest 自己寫入 `/app/results`；backtest 不連 `ccurr-dbwriter`、不進 live DB write path。若未來需要入庫，必須由獨立、明確授權的 offline exporter 在回測程序外執行，不屬本 Blueprint 的 live dbwriter contract。

---

## 5.3 Crash-window recovery

- Entry response unknown：保留 `clientOrderId` 與 pending state；UnknownLoop 查 Binance `/order`，不得直接產生新 order。
- Entry filled/OCO missing：OcoLoop 每 10 秒掃 `order:pending_oco:*`，依 executed/fee/filter safe quantity 補送。
- OCO 未成功前不得 DEL pending key；retry 10 次或 30 分鐘觸發 critical/manual intervention。

---



| 來源                  | 目標               | 協定    | 內容                       | 模式           |
| --------------------- | ------------------ | ------- | -------------------------- | -------------- |
| `ccurr-k*`          | 幣安               | HTTPS   | 抓 K 線                    | —             |
| `ccurr-k*`          | ClickHouse         | TCP     | 讀歷史                     | 直連           |
| `ccurr-k*`          | `ccurr-dbwriter` | UDS     | 寫 K 線                    | async          |
| `ccurr-k*`          | Redis              | TCP     | 心跳                       | —             |
| `ccurr-strategy`    | ClickHouse         | TCP     | 讀 K 線                    | 直連           |
| `ccurr-strategy`    | Redis              | TCP     | 讀持倉、發信號             | —             |
| `ccurr-strategy`    | `ccurr-dbwriter` | UDS     | 寫策略績效、執行記錄       | async          |
| `ccurr-strategy`    | Redis              | Pub/Sub | 訂閱`config:changed`     | —             |
| `ccurr-executor`    | Redis              | TCP     | 訂閱信號                   | —             |
| `ccurr-executor`    | `ccurr-risk`     | UDS     | 風控檢查                   | sync           |
| `ccurr-executor`    | `ccurr-trader`   | UDS     | 下單、OTOCO                | sync           |
| `ccurr-executor`    | `ccurr-dbwriter` | UDS     | 寫 order_log               | **sync** |
| `ccurr-order`       | `ccurr-trader`   | UDS     | 查訂單、取消               | sync           |
| `ccurr-order`       | `ccurr-dbwriter` | UDS     | 寫 trades                  | **sync** |
| `ccurr-order`       | Redis              | TCP     | 寫穿持倉、發事件           | —             |
| `ccurr-order`       | Redis              | TCP     | ZSET 超時佇列              | —             |
| `ccurr-accountsync` | `ccurr-trader`   | UDS     | 查餘額、訂單、價格         | sync           |
| `ccurr-accountsync` | 幣安 REST          | HTTPS   | 查 exchangeInfo            | —             |
| `ccurr-accountsync` | `ccurr-dbwriter` | UDS     | 寫 symbols                 | sync           |
| `ccurr-accountsync` | Redis              | TCP     | 寫快照、發信號             | —             |
| `ccurr-risk`        | Redis              | TCP     | 只讀（不呼叫任何人）       | —             |
| `ccurr-override`    | `ccurr-dbwriter` | UDS     | 寫 emergency_log           | **sync** |
| `ccurr-override`    | Redis              | TCP     | 發緊急信號                 | —             |
| `ccurr-websocket`   | 幣安 WS            | WSS     | 訂閱行情                   | —             |
| `ccurr-websocket`   | 幣安 REST          | HTTPS   | 熱門幣排名                 | —             |
| `ccurr-websocket`   | Redis              | TCP     | 發布行情指標               | —             |
| `ccurr-telegram`    | 各容器             | UDS     | 指令路由                   | sync           |
| `ccurr-telegram`    | `ccurr-dbwriter` | UDS     | 寫 telegram_log、audit_log | sync           |
| `ccurr-telegram`    | Redis              | TCP     | 訂閱告警                   | —             |
| `ccurr-telegram`    | Redis              | Pub/Sub | 發布`config:changed`     | —             |
| `ccurr-monitor`     | Redis              | TCP     | 讀心跳、統計               | —             |
| `ccurr-monitor`     | Redis              | TCP     | 寫降級狀態                 | —             |
| `ccurr-monitor`     | Redis              | Pub/Sub | 發告警                     | —             |
| `ccurr-backtest`    | ClickHouse         | TCP     | 讀歷史 K 線（offline preload） | 直連唯讀           |
| `ccurr-backtest`    | `/app/results`     | filesystem | 寫 JSON/HTML 回測結果；不連 dbwriter、不進 live DB write path | offline only |

 **UDS Socket 路徑** ：

| 容器               | Socket                     |
| ------------------ | -------------------------- |
| `ccurr-trader`   | `/sockets/trader.sock`   |
| `ccurr-dbwriter` | `/sockets/dbwriter.sock` |
| `ccurr-risk`     | `/sockets/risk.sock`     |
| `ccurr-override` | `/sockets/override.sock` |
| `ccurr-strategy` | `/sockets/strategy.sock` |
| `ccurr-monitor`  | `/sockets/monitor.sock`  |
| `ccurr-backtest` | `/sockets/backtest.sock` |

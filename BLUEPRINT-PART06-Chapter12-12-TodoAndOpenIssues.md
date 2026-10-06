# 第 12 章：待辦與開放問題

> 本章整理整個設計過程中的待辦事項、開放問題、未來優化方向，以及後續行動建議。

---

## 12.0 章節導覽

| 類別                        | 說明                       |
| --------------------------- | -------------------------- |
| **12.1 已定稿項目**   | 確認完成、可直接生成程式碼 |
| **12.2 待驗證假設**   | 需要實測才能確認的設計     |
| **12.3 待決策問題**   | 需要你決定才能繼續         |
| **12.4 未來優化方向** | 第一版不做，未來可加       |
| **12.5 已知風險**     | 設計上的潛在風險           |
| **12.6 後續行動建議** | 下一步該做什麼             |

---

## 12.1 已定稿項目

### 12.1.1 架構與容器

| 項目              | 狀態    | 備註                   |
| ----------------- | ------- | ---------------------- |
| 16 個容器職責劃分 | ✅ 定稿 | 見第 0 章              |
| 容器通訊協定      | ✅ 定稿 | UDS / Redis / 外部 API |
| 啟動順序          | ✅ 定稿 | 見第 6.15 節           |
| 依賴矩陣          | ✅ 定稿 | 見第 6.16 節           |
| 部署檢查清單      | ✅ 定稿 | 見第 6.17 節           |

### 12.1.2 六大通用機制

| 機制       | 狀態    | 備註                      |
| ---------- | ------- | ------------------------- |
| Trace ID   | ✅ 定稿 | 24h TTL                   |
| 分散式鎖   | ✅ 定稿 | SET NX EX + Lua           |
| 事件匯流排 | ✅ 定稿 | EventEnvelope             |
| 審計日誌   | ✅ 定稿 | 統一寫 audit_log          |
| 優雅降級   | ✅ 定稿 | 由 monitor 維護           |
| 動態配置   | ✅ 定稿 | MariaDB + Redis + Pub/Sub |

### 12.1.3 資料庫 Schema

| 資料庫               | 狀態    | 備註                                     |
| -------------------- | ------- | ---------------------------------------- |
| ClickHouse（3 張表） | ✅ 定稿 | pricesall / symbol_metadata / kline_gaps |
| MariaDB（20 張表）   | ✅ 定稿 | 含 runtime_config / audit_log            |
| Redis Key（14 類）   | ✅ 定稿 | 見第 4 章                                |

### 12.1.4 策略引擎（契約收斂後的狀態）

| 項目             | 狀態    | 備註         |
| ---------------- | ------- | ------------ |
| Step 1~9 規格    | ✅ 定稿 | 見第 7 章；介面引用 Chapter 9 canonical contract |
| 引擎架構（三層） | ✅ 定稿 | 見第 8 章；編排不得重定義插件介面 |
| 策略插件介面     | ⚠️ 契約已指定、待驗證 | Chapter 9 `Strategy Plugin Contract v1`；需完成全文一致性與 contract tests |
| 回測接口         | ⚠️ 實作遵循契約、待驗證 | 見第 10 章；live/backtest 使用同一 constructor/lifecycle |
| 參數總表         | ✅ 定稿 | 見第 7.10 節 |

### 12.1.5 生成順序

| 項目            | 狀態    | 備註         |
| --------------- | ------- | ------------ |
| 12 階段生成順序 | ✅ 定稿 | 見第 11 章   |
| Prompt 範本     | ✅ 定稿 | 每階段有範本 |
| 驗收標準        | ✅ 定稿 | 每階段有清單 |

### 12.1.6 策略插件唯一契約（Strategy Plugin Contract v1）

| 契約項目 | 唯一來源 | 收斂規則 |
|---|---|---|
| `BaseStrategy` / constructor / lifecycle | Chapter 9 §§9.1、9.0 | live/backtest 一律使用 `(config, context_builder)` |
| `BaseStep` / Step 1~8 | Chapter 9 §9.2 | Chapter 7/8 只描述業務流程或引用 |
| `StrategyContext` / `Clock` | Chapter 9 §9.3 | `now_ms()` 委派注入 clock，不得直接 wall-clock |
| `Candidate` / `Signal` | Chapter 9 §9.4 | `TradingCandidate` 舊名不得形成第二 schema |
| Provider / broker / backtest adapter | Chapter 9–10 | Chapter 10 實作 canonical contract |

**驗收門檻**：在全文搜尋確認沒有未標示的重複 normative definition、constructor 呼叫一致、Chapter 7/8/10/11 都引用 Chapter 9，且完成 contract/API、model、clock 與 live/backtest parity tests 前，不得把插件契約標為完全定稿。

### 12.1.7 時間與數值型別契約（第 2 步）

| 項目 | 狀態 | 驗收條件 |
|---|---|---|
| UTC epoch-ms 與 duration 單位 | ⚠️ 契約已指定、待驗證 | domain/API/Redis 使用 13 位 `int`；duration 明確 `_ms`/`_sec` |
| Decimal 與百分比單位 | ⚠️ 契約已指定、待驗證 | canonical models 禁止 float；`_pct` 是百分比點，RVOL 是 Decimal 倍數 |
| Step 2 typed output | ⚠️ 契約已指定、待驗證 | `SpikeResult`/`SpikeObservation`、slot/closed/elapsed/missing-data 規則一致 |
| DB timestamp boundary | ⚠️ 契約已指定、待驗證 | `DateTime64(3)`/`DATETIME(3)` 由 UTC adapter 雙向轉換，無 schema migration |

**本步驗收門檻**：全文不得存在未標示的 Step 2 `list[dict]`、canonical model float、未標單位 duration 或策略路徑的直接 wall-clock；需完成 Decimal/timestamp round-trip、threshold boundary、zero-denominator、closed-slot 與 live/backtest model parity tests。

### 12.1.8 Spot Order Intent 與 OCO Lifecycle 契約（第 3 步）

| 項目 | 狀態 | 唯一決定 |
|---|---|---|
| 產品 | ✅ 已鎖定 | 僅 Binance Spot；不使用 `reduceOnly` |
| Order Intent | ✅ 已鎖定 | Signal/OrderIntent 同時供 live 與 backtest 使用；下游 adapter 分流 |
| OCO owner | ✅ 已鎖定 | `ccurr-order` 管理 lifecycle；executor 初始化；trader 是唯一 Binance 出口 |
| 冪等鍵 | ✅ 已鎖定 | executor 產生 `{strategyId}-{uuid4}` `clientOrderId`；retry 重用 |
| Partial Fill | ✅ 已鎖定 | fallback OCO 使用實際 `executed_qty`，依 fee/filter 校正 |
| 原子 OTOCO fallback | ✅ 已鎖定 | `Entry + post-fill OCO`，不得宣稱原子 OTOCO |
| Symbol capability/filter | ✅ 已鎖定 | accountsync → risk → Binance REST 三層驗證 |

### 12.1.9 Candidate Lifecycle 與 Redis 狀態契約（第 4 步）

| 項目 | 狀態 | 唯一決定 |
|---|---|---|
| Candidate authoritative source | ✅ 已鎖定 | MariaDB `strategy_candidates` |
| Redis canonical entity | ✅ 已鎖定 | Hash `strategy:candidate_data`，field=`trace_id`，TTL 7d |
| SEMI review queue | ✅ 已鎖定 | `strategy:pending_reviews` ZSET + `strategy:pending_review:active` Set |
| MANUAL | ✅ 已鎖定 | 只寫 Candidate Hash/message map，不進 review ZSET，不自動 expire |
| SEMI timeout | ✅ 已鎖定 | `TIMEOUT_AUTO`/`AUTO_APPROVED`，執行 Step 8；CANCEL 僅為磨合期運行配置 |
| Confirm/Timeout race | ✅ 已鎖定 | 共用 10s review lock、active Set 二次檢查、Pipeline/Lua atomic cleanup |
| Redis TTL | ✅ 已鎖定 | TTL 只清理熱狀態，不代表 terminal；reconciliation 依 MariaDB 恢復 |
| custom_tp | ✅ 已鎖定 | Confirm 時 Decimal 驗證並鎖入 Signal；AUTO/timeout 使用預設值 |
| Notification failure | ✅ 已鎖定 | Candidate lifecycle 不阻塞；一般告警進 `telegram:buffer:{tg_id}`，critical 做 dedup/degradation/audit |
| Restart reconciliation | ✅ 已鎖定 | Candidate 由 strategy 依 MariaDB 恢復；accountsync 恢復資產；order 恢復訂單/OCO |

**驗收門檻**：確認/逾時競態不得雙重執行 Step 8；MANUAL 不得被 timeout worker 處理；Redis TTL 不得被當作 terminal；所有 terminal transition 都要有 MariaDB status 與 reconciliation 規則。

### 12.1.10 風控與 Position Sizing 契約（第 5 步）

| 項目 | 狀態 | 唯一決定 |
|---|---|---|
| V1 `weight_pct` | ✅ 已鎖定 | Capital Allocation Weight；S/R FLIP=10%、ORIGIN_LOW=5% |
| R17 | ✅ 已鎖定 | strategy allocation → trade amount → original quantity |
| R06 | ✅ 已鎖定 | 以 entry/stop/fee 計算，max risk 具最高否決權，預設 2% |
| R12/R14 | ✅ 已鎖定 | 向下截斷後重跑 minQty/minNotional；不足一律 DENY，不補大 |
| R13 | ✅ 已鎖定 | 以 `balance:USDT.free` 與含費用 entry cost 檢查 |
| Fee/OCO | ✅ 已鎖定 | BNB 0.075%；非 BNB `executed_qty × 0.999` 再 quantize/filter |
| Live/Backtest | ✅ 已鎖定 | 共用 RiskCalculator 商業契約，只替換 account/filter provider |
| 未來 S6 | ⚠️ 未啟用 | Risk-Parity 只作未來優化，不得混入 V1 |

**驗收門檻**：R17 → R06 → R12 → R14 → R13 順序明確；allocation 不得覆寫 max risk；MIN_NOTIONAL/餘額不足不可自動放大；Partial Fill OCO 使用 safe executed quantity 並保留 pending key；live/backtest 結果在等價輸入下具 parity。

---

### 12.1.11 跨容器資料、DB 與通訊契約（第 6 步）

| 項目 | 狀態 | 唯一決定 |
|---|---|---|
| Authoritative source | ✅ 已鎖定 | order/trade/audit→MariaDB；asset→Binance；Candidate→MariaDB；Kline→ClickHouse；config→MariaDB |
| Redis writer | ✅ 已鎖定 | business-state key 每 key 唯一主要 writer；`position:*` 僅允許 order write-through + accountsync correction；`price:latest:*` 唯一由 websocket 寫入；trace keys 為 append-only telemetry 多 writer 例外；pending order/OCO 由 executor 建立、order 更新/終結/recovery |
| Binance routing | ✅ 已鎖定 | private/trading→trader；public kline→k*；public WS→websocket；exchangeInfo→accountsync exception |
| DB read/write | ✅ 已鎖定 | writes→dbwriter；direct SELECT readers 受 matrix 限制；executor/trader/telegram 禁止 DB |
| Backtest exception | ✅ 已鎖定 | boot data/config fatal；sweep isolate；結果一律寫 `/app/results`；不連 Redis、dbwriter、live DB write path |
| Event reliability | ✅ 已鎖定 | lossy telemetry/latest-value；reliable events state/DB-backed with recovery |
| Reconciliation | ✅ 已鎖定 | accountsync 15s；order Main 10s/Unknown 30s/OCO 10s；strategy candidate recovery |
| Crash window | ✅ 已鎖定 | UNKNOWN 查詢且重用 clientOrderId；pending OCO 成功前不刪除 |

### 12.1.13 Steps 1–7 整合發布狀態

| 項目 | 狀態 | 說明 |
|---|---|---|
| Integrated contract release | ⚠️ INTEGRATION | 見 `BLUEPRINT-MANIFEST.yaml` 與 `BLUEPRINT-CONTRACT-INDEX.md` |
| G0–G5 documentation gates | ⚠️ 待驗證 | 通過前不得標記 VERIFIED/RELEASED |
| G6 release approval | ⚠️ 未完成 | 需明確批准後才可 production generation |
| Known blockers | ⚠️ BLOCKED/CONDITIONAL | stop-buffer、完整 schema inventory、parity/contract evidence 等仍須確認 |

**狀態規則**：`DRAFT → INTEGRATION → VERIFIED → RELEASED`；衝突或證據不足時使用 `BLOCKED`。Chapter 12 的「已定稿」只表示局部設計決策，不得覆寫 manifest 的整體 release status。

---



| 項目 | 狀態 | 唯一決定 |
|---|---|---|
| Container inventory | ✅ 已鎖定 | 22 = 16 business + 3 infrastructure + 3 operations |
| Startup layers | ✅ 已鎖定 | infrastructure → dbwriter/trader → reconciliation/ingestion → core → interface/ops |
| Network egress | ✅ 已鎖定 | trader→Tailscale/AWS；k*→macvlan；websocket/telegram→local NAT；其餘 live core no WAN |
| Secrets | ✅ 已鎖定 | Binance secrets only trader；backtest no live secrets |
| Readiness | ✅ 已鎖定 | infrastructure health、reconciliation、account.synced、order UNKNOWN/pending-OCO recovery 完成前 OPEN DENY |
| Persistence | ✅ 已鎖定 | Redis AOF/RDB、MariaDB/ClickHouse named volumes、fallback volume |
| Fault policy | ✅ 已鎖定 | DENY/retry/fallback/degraded matrix；Telegram buffer；backtest `/app/results` |
| Backtest isolation | ✅ 已鎖定 | independent profile；no live sockets/macvlan/Redis/dbwriter/Binance |

**驗收門檻**：Compose/profile、network、healthcheck、secret、volume、startup/restart、readiness 與 fault matrix 必須一致；不得因 backtest 或運維容器影響 live trading。

---


### 12.2.1 技術假設

| #  | 假設                             | 驗證方式     | 風險 |
| -- | -------------------------------- | ------------ | ---- |
| A1 | UDS 跨容器通訊穩定               | 部署後測試   | 低   |
| A2 | Redis ZSET 延遲佇列效能足夠      | 壓力測試     | 低   |
| A3 | ClickHouse 缺口偵測 SQL 效能     | 大資料量測試 | 中   |
| A4 | macvlan 綁定三條寬頻穩定         | 實測 24h     | 中   |
| A5 | Tailscale exit node 固定 IP 穩定 | 實測 7 天    | 中   |
| A6 | 幣安 OTOCO API 支援所有交易對    | 逐幣測試     | 高   |
| A7 | 幣安 API Rate Limit 管理足夠     | 實測         | 中   |

### 12.2.2 業務假設

| #  | 假設                          | 驗證方式    | 風險 |
| -- | ----------------------------- | ----------- | ---- |
| B1 | Phase 1 判定標準能篩出好幣    | 回測 1 年   | 高   |
| B2 | Phase 2 縮量回踩勝率高        | 回測 1 年   | 高   |
| B3 | A 區（S/R Flip）勝率高於 B 區 | 實盤 3 個月 | 中   |
| B4 | 資金權重 10% / 5% 合理        | 實盤 3 個月 | 中   |
| B5 | 停損緩衝 0.5% 足夠            | 歷史假設（SUPERSEDED；V1 canonical 為 D7 統一 1.0%） | 中   |
| B6 | 冷卻 24 小時合理              | 實盤 1 個月 | 低   |
| B7 | SEMI 超時 10 分鐘合理         | 實盤 1 個月 | 低   |

### 12.2.3 驗證優先順序

```text
最高優先（實盤前必須驗證）：

1. A6：OTOCO API 支援（若某些幣不支援，需確認 Fallback 流程）
2. B1：Phase 1 判定（用歷史資料回測）
3. B2：Phase 2 判定（用歷史資料回測）

次高優先（實盤小額驗證）：
4. B3：A 區 vs B 區勝率
5. B5：停損緩衝
6. A7：Rate Limit

最後驗證：
7. A4：macvlan
8. A5：Tailscale
9. B4：資金權重
10. B6/B7：冷卻與超時
```

---

## 12.3 待決策問題

### 12.3.1 需要你決定的問題

| 問題 | 選項                                 | 建議          | 影響範圍 |
| ---- | ------------------------------------ | ------------- | -------- |
| D1   | 第一版是否啟用 L3（aggTrade）        | 是 / 否       | 否       |
| D2   | 第一版是否啟用 1d 均線共振           | 是 / 否       | 否       |
| D3   | 第一版是否啟用 Docker 重啟           | 是 / 否       | 否       |
| D4   | 是否啟用 Log 讀取端點                | 是 / 否       | 否       |
| D5   | MANUAL 模式是否提供手動進場按鈕      | 是 / 否       | 是       |
| D6   | SEMI 超時後行為                      | AUTO / CANCEL | AUTO     |
| D7   | 停損緩衝是否分級                     | 是 / 否       | 否（v1） |
| D8   | 是否記錄 strategy_run_log 到 MariaDB | 是 / 否       | 是       |
| D9   | 是否啟用 ccurr-backtest 的 UDS API   | 是 / 否       | 是       |

### 12.3.2 建議決策

**D1：L3（aggTrade）**

* 建議 **否**
* 理由：第一版簡單為主，L3 數據量大
* 未來需要訂單流分析時再開

**D2：1d 均線共振**

* 建議 **否**
* 理由：均線落後，急漲急跌時跟不上
* 未來穩定後可實驗

**D3：Docker 重啟**

* 建議 **否**
* 理由：掛載 docker.sock 等於給容器 root 權限
* 手動 `docker restart` 即可

**D4：Log 讀取端點**

* 建議 **否**
* 理由：需掛載宿主機日誌目錄
* 用 `docker logs` 即可

**D5：MANUAL 手動進場按鈕**

* 建議 **是**
* 理由：保留系統統一介面價值
* 點擊時重新檢查價格

**D6：SEMI 超時行為**

* 建議 **AUTO**
* 理由：機會不等人
* 但你需先熟悉系統再啟用

**D7：停損緩衝分級**

* 建議 **第一版不分級** ，統一 1.0%
* 理由：簡化邏輯
* 未來再分級（大 0.2% / 中 0.5% / 小 2%）

**D8：策略執行記錄**

* 建議 **是**
* 理由：除錯命脈
* 每小時 flush，關閉前強制 flush

**D9：回測 UDS API**

* 建議 **是**
* 理由：可用 Telegram 觸發回測
* 從 CLI 也可


### 12.3.3 最終決策（已確認）

| #  | 問題                                 | 最終決定                            |
| -- | ------------------------------------ | ----------------------------------- |
| D1 | 第一版是否啟用 L3（aggTrade）        | **否**                        |
| D2 | 第一版是否啟用 1d 均線共振           | **否**                        |
| D3 | 第一版是否啟用 Docker 重啟           | **否**                        |
| D4 | 是否啟用 Log 讀取端點                | **否**                        |
| D5 | MANUAL 模式是否提供手動進場按鈕      | **是**                        |
| D6 | SEMI 超時後行為                      | **AUTO**                      |
| D7 | 停損緩衝是否分級                     | **第一版不分級**（統一 1.0%） |
| D8 | 是否記錄 strategy_run_log 到 MariaDB | **是**                        |
| D9 | 是否啟用 ccurr-backtest 的 UDS API   | **是**                        |

**最終決策已於藍圖定稿時確認，作為第一版實作基準。**


## 12.4 未來優化方向

### 12.4.1 短期（1~3 個月）

| #  | 項目             | 說明                                   | 優先級 |
| -- | ---------------- | -------------------------------------- | ------ |
| S1 | 策略績效統計     | 從 strategy_perf 分析 A 區 vs B 區勝率 | 高     |
| S2 | 參數自動調優     | 用參數掃描找最佳配置                   | 中     |
| S3 | 多策略並行       | 序列執行改並行                         | 中     |
| S4 | 更多技術指標     | 加入 Bollinger Bands、KDJ 等           | 低     |
| S5 | 更精細的滑價模型 | 回測用訂單簿模擬                       | 低     |
| S6 | 風險等價頭寸計算 | R17 改為「基於停損距離」計算 qty       | 高     |

#### 優化 S6：風險等價頭寸計算（Risk-Parity Position Sizing）

**問題**：
V1 的 R17 採用固定金額下單法：

```text
qty = (strategy_fund * weight_pct / 100) / current_price
```

這導致不同停損距離的幣種，實際虧損金額差異巨大：

- 幣 A：停損 2%，虧損 = 倉位 × 2%
- 幣 B：停損 10%，虧損 = 倉位 × 10%（是幣 A 的 5 倍）

**優化方案**：
改為基於風險的頭寸計算：

```text
risk_amount = total_value * max_risk_per_trade_pct / 100
stop_distance = entry_price - stop_loss_price
qty = min(
    risk_amount / stop_distance,
    (strategy_fund * weight_pct / 100) / current_price,  # 上限
)
```

**優點**：

- 每筆交易的風險金額相同
- 不受停損距離影響
- 業界標準做法

**實作時機**：
實盤 3 個月後，累積足夠 `strategy_perf` 數據再切換。

### 12.4.2 中期（3~6 個月）

| #  | 項目               | 說明                   | 優先級 |
| -- | ------------------ | ---------------------- | ------ |
| M1 | 多交易所支援       | 加入 OKX、Bybit        | 中     |
| M2 | 合約交易支援       | 支援幣安合約           | 中     |
| M3 | WebSocket 深度增量 | 用增量取代快照         | 低     |
| M4 | 訂單流分析         | 用 aggTrade 做微觀分析 | 低     |
| M5 | ML 模型輔助        | 用 ML 預測突破成功率   | 低     |
| M6 | 多使用者支援       | Telegram 多使用者管理  | 低     |

### 12.4.3 長期（6 個月+）

| #  | 項目         | 說明                   | 優先級 |
| -- | ------------ | ---------------------- | ------ |
| L1 | 跨交易所套利 | 同時監控多交易所       | 低     |
| L2 | 資金費率套利 | 現貨 + 合約對沖        | 低     |
| L3 | 高頻交易     | 用 Rust 寫熱路徑       | 低     |
| L4 | 分散式部署   | 多機部署               | 低     |
| L5 | K8s 遷移     | 從 Docker Compose 遷移 | 低     |

### 12.4.4 具體優化項目

#### 優化 1：策略績效統計

```text
新增功能：

- 每日統計 A 區 vs B 區勝率
- 統計不同 support_type 的平均報酬
- 統計不同參數組合的表現
- 寫入 strategy_perf 表

用途：

- 決定是否調整資金權重
- 決定是否停用某類進場
- 決定是否調整參數
```

#### 優化 2：參數自動調優

```text
新增功能：

- 每週執行參數掃描
- 用 walk-forward analysis
- 找「高原」而非「尖峰」
- 自動更新建議參數

注意：

- 需避免過擬合
- 需人工確認
```

#### 優化 3：更精細的滑價模型

```text
新增功能：

- 回測時模擬訂單簿深度
- 不同金額的滑價不同
- 大單分批模擬
- 更真實的成交率

需要：

- 歷史 depth 快照
- 或簡化的滑價公式
```

## 12.5 已知風險

### 12.5.1 技術風險

| #  | 風險                | 影響         | 緩解                    |
| -- | ------------------- | ------------ | ----------------------- |
| R1 | 幣安 API 變更       | 系統無法運作 | 追蹤公告，預留 Fallback |
| R2 | OTOCO 某些幣不支援  | 需 Fallback  | 已設計 Fallback 流程    |
| R3 | Redis 掛掉          | 系統停擺     | Redis 持久化 + 監控告警 |
| R4 | ClickHouse 資料損壞 | K 線遺失     | 定期備份 + 缺口偵測     |
| R5 | 網路斷線            | 無法交易     | Tailscale + 多寬頻      |
| R6 | 幣安限流            | 暫時無法交易 | Rate Limit 管理 + 退避  |
| R7 | 伺服器硬體故障      | 系統停擺     | 定期備份 + 監控         |

### 12.5.2 業務風險

| #   | 風險         | 影響         | 緩解                  |
| --- | ------------ | ------------ | --------------------- |
| R8  | 策略失效     | 虧損         | 小額實盤驗證 + 熔斷   |
| R9  | 參數過擬合   | 實盤表現差   | 樣本外測試            |
| R10 | 極端行情     | 大幅虧損     | 風控熔斷 + 緊急平倉   |
| R11 | 幣安下架幣種 | 持倉無法平倉 | 監控下架公告          |
| R12 | 黑天鵝事件   | 系統崩潰     | 手動干預 + 幣安 App   |
| R13 | 粉塵幣累積   | 資產浪費     | BNB Keeper + 定期清理 |

### 12.5.3 操作風險

| #   | 風險          | 影響     | 緩解                     |
| --- | ------------- | -------- | ------------------------ |
| R14 | 誤操作平倉    | 損失     | 二次確認                 |
| R15 | Telegram 洩漏 | 被盜用   | 白名單 + 權限分級        |
| R16 | API Key 洩漏  | 資金被盜 | 只允許固定 IP + 關閉提幣 |
| R17 | 參數誤改      | 系統異常 | 審計 + 回滾              |
| R18 | 忘記監控      | 錯過問題 | Telegram 告警            |

### 12.5.4 風險優先級

```text
最高（立即緩解）：

- [ ] R14：誤操作平倉 → 已有二次確認
- [ ] R16：API Key 洩漏 → 已限制 IP
- [ ] R10：極端行情 → 已有熔斷

次高（實盤前緩解）：

- [ ] R8：策略失效 → 小額驗證
- [ ] R9：參數過擬合 → 樣本外測試
- [ ] R3：Redis 掛掉 → 持久化 + 監控

中（實盤後緩解）：

- [ ] R1：API 變更 → 追蹤公告
- [ ] R4：ClickHouse 損壞 → 定期備份
- [ ] R13：粉塵幣 → BNB Keeper

低（長期緩解）：

- [ ] R7：硬體故障 → 定期備份
- [ ] R11：下架幣種 → 監控公告
- [ ] R17：參數誤改 → 審計 + 回滾
```

## 12.6 後續行動建議

### 12.6.1 立即行動（本週）

| #  | 行動                      | 產出                  | 時程 |
| -- | ------------------------- | --------------------- | ---- |
| A1 | 確認 12.3 的 9 個決策     | 決策清單              | 1 天 |
| A2 | 建立 Git repo             | 專案骨架              | 1 天 |
| A3 | 執行階段 0（環境準備）    | 骨架 + docker-compose | 2 天 |
| A4 | 執行階段 1（shared 基礎） | shared 模組           | 3 天 |

### 12.6.2 短期行動（1 個月）

| #  | 行動          | 產出                                            | 時程 |
| -- | ------------- | ----------------------------------------------- | ---- |
| B1 | 執行階段 2~5  | shared 六大機制 + DB Schema + trader + dbwriter | 2 週 |
| B2 | 執行階段 6    | 資料服務（6 容器）                              | 1 週 |
| B3 | 執行階段 7~8  | 決策與執行 + 策略引擎                           | 1 週 |
| B4 | 執行階段 9~10 | 介面與監控 + 回測                               | 3 天 |

### 12.6.3 中期行動（3 個月）

| #  | 行動              | 產出       | 時程   |
| -- | ----------------- | ---------- | ------ |
| C1 | 執行階段 11       | 整合測試   | 1 週   |
| C2 | 執行階段 12       | 部署上線   | 1 週   |
| C3 | 回測 1 年資料     | 績效報告   | 1 週   |
| C4 | MANUAL 模式運行   | 觀察 7 天  | 1 週   |
| C5 | SEMI 模式小額實盤 | 觀察 7 天  | 1 週   |
| C6 | SEMI 模式正常金額 | 觀察 30 天 | 1 個月 |

### 12.6.4 上線策略

```text
第 1~7 天：MANUAL 模式

- 只通知，不自動下單
- 驗證信號品質
- 驗證 Telegram 互動

第 8~14 天：SEMI 模式（小額）

- 人工確認，小額實盤
- 每次交易金額為正常金額的 10%
- 驗證完整流程

第 15~30 天：SEMI 模式（正常金額）

- 人工確認，正常金額
- 驗證風控與執行

第 31 天+：AUTO 模式（可選）

- 全自動
- 前提：前 30 天表現良好
- 需持續監控
```

### 12.6.5 監控指標

 **每日檢查** ：

| 指標          | 目標       | 行動           |
| ------------- | ---------- | -------------- |
| 帳戶總值      | 穩定或成長 | 若下跌 5% 檢查 |
| 交易筆數      | 合理       | 若過多檢查參數 |
| 勝率          | > 50%      | 若過低檢查策略 |
| 最大回撤      | < 20%      | 若過大停用策略 |
| 未平倉數      | < 5        | 若過多檢查信號 |
| critical 告警 | 0          | 若有立即排查   |

 **每週檢查** ：

| 指標             | 目標  | 行動           |
| ---------------- | ----- | -------------- |
| 夏普比率         | > 1.0 | 若過低調參數   |
| Profit Factor    | > 1.5 | 若過低檢查策略 |
| A 區 vs B 區勝率 | 分析  | 調整資金權重   |
| 錯誤類型統計     | 減少  | 修復常見錯誤   |

 **每月檢查** ：

| 指標       | 目標   | 行動         |
| ---------- | ------ | ------------ |
| 策略績效   | 穩定   | 決定是否繼續 |
| 系統穩定性 | > 99%  | 修復問題     |
| 資料完整性 | 無缺口 | 補齊缺口     |
| 備份驗證   | 完整   | 測試還原     |

---

## 12.7 開放問題（長期）

### 12.7.1 策略相關

| #  | 問題                   | 說明         | 何時處理      |
| -- | ---------------------- | ------------ | ------------- |
| O1 | 是否要加入更多策略？   | 目前只有一個 | 實盤 3 個月後 |
| O2 | 如何評估策略衰減？     | 市場變化     | 實盤 6 個月後 |
| O3 | 是否要動態調整參數？   | 適應市場     | 實盤 6 個月後 |
| O4 | 是否要加入 ML 模型？   | 提升勝率     | 實盤 1 年後   |
| O5 | 是否要支援多策略組合？ | 分散風險     | 實盤 6 個月後 |

### 12.7.2 技術相關

| #   | 問題                                | 說明             | 何時處理     |
| --- | ----------------------------------- | ---------------- | ------------ |
| O6  | 是否要遷移到 K8s？                  | 擴展性           | 多機部署時   |
| O7  | 是否要用 Rust 寫熱路徑？            | 效能             | 高頻需求時   |
| O8  | 是否要加入更多資料庫？              | 例如 TimescaleDB | 資料量過大時 |
| O9  | 是否要用 gRPC 取代 UDS？            | 效能             | 跨機通訊時   |
| O10 | 是否要用 Kafka 取代 Redis Pub/Sub？ | 可靠性           | 需要重播時   |

### 12.7.3 業務相關

| #   | 問題                 | 說明     | 何時處理           |
| --- | -------------------- | -------- | ------------------ |
| O11 | 是否要支援多交易所？ | 分散風險 | 單交易所依賴過高時 |
| O12 | 是否要支援合約？     | 槓桿交易 | 現貨穩定後         |
| O13 | 是否要支援多使用者？ | 團隊使用 | 需要時             |
| O14 | 是否要開放 API？     | 對外服務 | 成熟後             |
| O15 | 是否要商業化？       | 販售服務 | 長期考慮           |

## 12.8 交付清單

### 12.8.1 已交付文件

| 章節     | 內容               | 狀態 |
| -------- | ------------------ | ---- |
| 交付說明 | 使用方式           | ✅   |
| 第 0 章  | 系統概覽           | ✅   |
| 第 1 章  | 全域約定           | ✅   |
| 第 2 章  | 六大通用機制       | ✅   |
| 第 3 章  | 資料庫 Schema      | ✅   |
| 第 4 章  | Redis Key 總表     | ✅   |
| 第 5 章  | Container 通訊總表 | ✅   |
| 第 6 章  | 各容器藍圖         | ✅   |
| 第 7 章  | Step 1~9           | ✅   |
| 第 8 章  | 引擎架構           | ✅   |
| 第 9 章  | 策略插件介面       | ✅   |
| 第 10 章 | 回測接口           | ✅   |
| 第 11 章 | AI 生成順序        | ✅   |
| 第 12 章 | 待辦與開放問題     | ✅   |

### 12.8.2 完整交付內容

 **你現在擁有的** ：

1. **完整系統設計** ：16 個容器、六大機制、策略引擎、回測系統
2. **資料庫 Schema** ：ClickHouse 3 張 + MariaDB 20 張
3. **Redis Key 規範** ：14 類別，完整列表
4. **通訊總表** ：UDS / Redis / 外部 API
5. **Docker Compose** ：可直接部署的編排檔
6. **AI 生成順序** ：12 階段，每階段有 Prompt 與驗收標準
7. **參數總表** ：所有可調參數
8. **部署檢查清單** ：部署前 / 後 / 安全

 **你可以做的** ：

1. 把本文件交給本地 AI，逐階段生成程式碼
2. 與多個 AI 討論特定設計（提供第 7 章策略部分）
3. 直接部署 `docker-compose.yml` 測試基礎設施
4. 從第 11 章的階段 0 開始

---

## 12.9 最後建議

### 12.9.1 給你的話

1. **不要急** ：這是複雜系統，一次做一件事
2. **先驗證假設** ：A6（OTOCO）、B1（Phase 1）、B2（Phase 2）最重要
3. **先 MANUAL** ：不要一開始就 AUTO
4. **小額實盤** ：先用 10% 金額測試
5. **持續監控** ：每天檢查關鍵指標
6. **保留退路** ：幣安 App 是最終保險
7. **記錄一切** ：所有決策、所有結果
8. **持續學習** ：市場會變，策略要進化

### 12.9.2 關鍵提醒

> **「先讓它能動，再讓它變好」**
>
> 不要一開始就追求完美。
> 第一版只要能跑、能交易、能記錄，就夠了。
> 其他優化留給未來。

### 12.9.3 最終交付

**本文件（`CCURR_MASTER_BLUEPRINT.md`）是你的完整設計藍圖。**

**下一步**：

1. 回答 12.3 的 9 個決策問題
2. 從第 11 章的階段 0 開始
3. 逐階段生成程式碼
4. 逐階段驗收
5. 整合測試
6. 部署上線

**祝你交易順利。**

---

## 第 12 章完成 ✅

**全部 13 個章節（0~12）已交付完成。**

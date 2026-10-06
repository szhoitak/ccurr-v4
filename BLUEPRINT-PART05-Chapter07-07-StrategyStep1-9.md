# 第 7 章：`ccurr-strategy` Step 1~9

> 本章定義策略引擎的九步篩選漏斗。所有規格已於先前討論中定稿。
> **策略 ID** ：`volume_breakout_pullback_v1`
> **策略名稱** ：Volume Breakout Pullback

---

## 7.0 策略總覽

### 7.0.1 策略定位

捕捉「帶量突破 → 縮量回踩 → 觸及支撐」的強勢幣種。

### 7.0.2 九步篩選漏斗

```text
Step 1：掃描全市貨幣（排除黑名單）
    ↓ ~320 個
Step 2：放量掃描（同槽位對比）
    ↓ ~15 個
Step 3：成交額檢查（近 24h ≥ 300 萬 USDT）
    ↓ ~8 個
Step 4：Phase 1 升幅期（多 timeframe 交叉驗證）
    ↓ ~3 個
Step 5：Phase 2 回踩期（三層守門員）
    ↓ ~2 個
Step 6：接近低價區（動態支撐區）
    ↓ ~1 個
Step 7：產生候選名單（去重 + 冷卻 + 分流）
    ↓ 1 個
Step 8：計算掛單價 + OTOCO 交易計畫
    ↓ 1 個 Signal
Step 9：掛單超時管理（由 ccurr-order 負責）
```

### 7.0.3 核心設計原則

| 原則                     | 說明                                              |
| ------------------------ | ------------------------------------------------- |
| 同槽位對比               | 4h / 1h RVOL 用「今天同一槽位 vs 過去同槽位」     |
| 多 timeframe 交叉驗證    | 1d 宏觀 + 4h 動能 + 1h 爆發                       |
| 動態支撐區               | 用「前高突破點」與「起漲點」，不用固定天數        |
| 一進一出                 | 每筆 trace_id 都是獨立的 1 Entry → 1 Exit         |
| 絕對取消                 | 超時不改價、不延長                                |
| 決策與風控分離           | strategy 發意圖，risk 核算絕對值                  |

## 7.1 Step 1：掃描全市貨幣

### 7.1.1 規格

```text
【Step 1 規格】

輸入：

- MariaDB symbols 表
- Redis blacklist:cache

篩選條件：

- enabled = 1
- status = 'TRADING'
- quote_asset = 'USDT'

黑名單匹配：

- 暫時只用 exact 匹配
- 日後再考慮 prefix / regex

處理：

1. 讀取所有符合條件的 symbol
2. 讀取黑名單快取
3. 對每個 symbol 檢查是否精確匹配黑名單
4. 排除匹配的
5. 回傳待篩選清單

輸出：

- list[str]：待監察 symbol 清單（~320 個）

快取：

- 貨幣清單快取 5 分鐘
- 黑名單快取 5 分鐘

錯誤處理：

- MariaDB 讀取失敗 → 用上次快取
- 黑名單讀取失敗 → 記錄 warning，仍繼續

預估輸出：

- 幣安 USDT 現貨交易對 ~350
- 黑名單排除 ~30
- 待監察 ~320
```

### 7.1.2 參數

| 參數                        | 預設 | 說明         |
| --------------------------- | ---- | ------------ |
| `symbol_cache_ttl_sec`    | 300  | 貨幣清單快取 |
| `blacklist_cache_ttl_sec` | 300  | 黑名單快取   |

---

## 7.2 Step 2：放量掃描

### 7.2.1 核心概念

 **同槽位對比** ：今天同一槽位 vs 過去同槽位，蘋果比蘋果。

**為什麼不用年化？**
金融市場成交量呈 U 型或事件驅動，線性推算會嚴重誤判（例如開盤半小時乘 48 倍會誤以為史詩級天量）。

### 7.2.2 三個 timeframe 的算法

**1d（不年化）**

```text
RVOL_1d_ma7  = current.volume_quote / ma7
RVOL_1d_ma20 = current.volume_quote / ma20
```

早上小就小，真實反映累積量。

**4h（同槽位對比）**

```text
RVOL_4h(槽位 X) = 今天槽位 X 的 4h 量 / 過去 7 天槽位 X 的 4h 量均值
```

4h 一天有 6 個槽位：`00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00`

**1h（同槽位對比）**

```text
RVOL_1h(槽位 X) = 今天槽位 X 的 1h 量 / 過去 7 天槽位 X 的 1h 量均值
```

1h 一天有 24 個槽位。

### 7.2.3 完整規格

```text
【Step 2 規格】

輸入：

- Step 1 的待監察清單
- ClickHouse pricesall（含 is_closed）

前置假設：
本步驟假設 ClickHouse 中的 K 線狀態是最新的：
- ccurr-k* 已強制重抓最近 N 根，確保剛收盤的 K 線 is_closed=1
- 詳見第 6.5.5 節「強制重抓」機制

處理：

對每個 symbol，對三個 timeframe：

【1d — 不年化】

1. 讀最近 21 根 1d K 線
2. current = klines[-1]（可能未完成）
3. 若 elapsed < 30 分鐘 → 跳過
4. ma7 = mean(klines[-8:-1].volume_quote)
5. ma20 = mean(klines[-21:-1].volume_quote)
6. rvol_ma7 = current.volume_quote / ma7
7. rvol_ma20 = current.volume_quote / ma20

【4h — 同槽位對比】

1. slot_ts = 最近完成的 4h 槽位
2. 讀最近 121 根 4h K 線
3. current = find(klines, slot_ts)
4. same_slot_7 = 過去 7 天同一槽位的 K 線
5. 若 len(same_slot_7) < 5 → 跳過
6. ma7 = mean(same_slot_7.volume_quote)
7. same_slot_20 = 過去 20 天同一槽位
8. 若 len(same_slot_20) < 15 → 跳過
9. ma20 = mean(same_slot_20.volume_quote)
10. rvol_ma7 = current.volume_quote / ma7
11. rvol_ma20 = current.volume_quote / ma20

【1h — 同槽位對比】

同 4h 邏輯，槽位為 UTC 整點
樣本需求：168 根（ma7）/ 480 根（ma20）

判定：

- 若 rvol_ma7 >= threshold_ma7（3.0）
  或 rvol_ma20 >= threshold_ma20（2.0）
  → 標記為「放量」

輸出：

`list[SpikeResult]`（canonical model 見 Chapter 9 §9.4.3）。每個 observation 必須使用 UTC K 線開盤 `slot_ts`、`is_closed: bool`、`elapsed_ms: int | None` 及 Decimal 數值欄位；不得輸出未定義 schema 的 `list[dict]`。

Step 2 數值與資料規則：

- `volume_quote`、`ma7`、`ma20`、RVOL 與 threshold 均使用 `Decimal`。
- `threshold_ma7`/`threshold_ma20` 是無單位 RVOL 倍數，例如 `Decimal("3.0")`，不是百分比。
- `_pct` 設定使用百分比點，例如 `Decimal("5.0")` 代表 5%；公式中明確除以 100。
- `elapsed_ms = context.now_ms() - slot_ts`；展示層如需分鐘，最後才由 `elapsed_ms / 60000` 計算，不作 canonical 欄位。
- `None` volume、零分母、重複或不對齊 slot、樣本不足、所需 K 線缺失均記錄原因並跳過該 timeframe；不得以 0 代替分母。
- threshold 比較採 `>=`，Decimal 計算使用共用 precision/rounding policy，不得先轉 float。
- `slot_ts` 必須為 UTC：1d 為 00:00、4h 為 00/04/08/12/16/20、1h 為整點。
- 1d 的 current 可未收盤，但必須標示 `is_closed=False`；4h/1h 使用最近完成槽位，若未確認收盤則跳過。
- 4h 使用 7 天/20 天同槽位窗口；1h 明確使用 168 根（7 天）/480 根（20 天），不得以「同 4h 邏輯」代替。


參數（Telegram 可調）：

- scan_interval_sec: 900
- threshold_ma7: Decimal("3.0")（RVOL 倍數）
- threshold_ma20: Decimal("2.0")（RVOL 倍數）
- min_elapsed_min_1d: 30（執行時轉為 `elapsed_ms = 1_800_000`）
- min_samples_7d: 5
- min_samples_20d: 15

錯誤處理：

- ClickHouse 讀取失敗 → 記錄 warning，跳過
- 樣本不足 → 記錄 debug，跳過
- 槽位缺失 → 用剩餘樣本（< 5 或 < 15 則跳過）
```

### 7.2.4 級別衝突處理

若只有 1d 放量，4h 與 1h 都沒放量：

| 檢查                                | 動作                   |
| ----------------------------------- | ---------------------- |
| `upper_wick > body * 1.5`         | REJECT（疑似高位派發） |
| `daily.close > daily.open * 1.05` | ACCEPT（溫和建倉）     |
| 其他                                | REJECT（放量不漲）     |

### 7.2.5 需要更新的 `ccurr-k*`

| Container     | 排程變更                                          |
| ------------- | ------------------------------------------------- |
| `ccurr-k4h` | 每 4 小時 →**每 1 小時（`minute=10`）**  |
| `ccurr-k1d` | 每 24 小時 →**每 1 小時（`minute=10`）** |

 **`history_lookback` 更新** ：

| Timeframe | 舊值 | 新值          |
| --------- | ---- | ------------- |
| 1d        | 250  | **30**  |
| 4h        | 250  | **150** |
| 1h        | 250  | **500** |
| 5m        | 250  | 250           |

---

## 7.3 Step 3：成交額檢查

### 7.3.1 規格

```text
【Step 3 規格】

輸入：

- Step 2 通過的 symbol 清單

處理：

對每個 symbol：
1. 讀最近 8 根 4h K 線（多讀 2 根做緩衝）
2. 過濾出「已完成」的（is_closed=1）
3. 取最近 6 根
4. 若樣本 < 4 → 跳過該 symbol
5. sum_volume = sum(k.volume_quote for k in last_6)
6. 若 sum_volume >= min_volume_24h_usdt → 通過

輸出：

`list[VolumeResult]`（canonical model 見 Chapter 9 §9.4.3）。本節的字典僅為欄位展示，不是第二套 schema。

參數（Telegram 可調）：

- min_volume_24h_usdt: 3000000
- volume_check_lookback_4h: 6
- min_volume_samples: 4

錯誤處理：

- ClickHouse 讀取失敗 → 記錄 warning，跳過
- 樣本不足 → 記錄 debug，跳過
- 4h K 線缺失 → 用剩餘樣本
```

### 7.3.2 設計決策

| 決策                              | 說明                                       |
| --------------------------------- | ------------------------------------------ |
| 用「近 6 根 4h」而非 1d K 線      | 避開未完成的 1d K 線                       |
| 保留 Step 2 放量的 timeframe 資訊 | 供後續 Step 參考                           |
| 統一用「近 24h 成交量」檢查       | 與 timeframe 無關，所有 symbol 一致標準    |

## 7.4 Step 4：Phase 1 升幅期

### 7.4.1 核心設計

三層交叉驗證：

```text
1d 宏觀保障（突破天花板 + 無長上影線）
    +
4h 核心動能（實質漲幅 ≥ 15% + 有放量）
    +
1h 爆發確認（有放量大陽線）
    =
Phase 1 確認
```

### 7.4.2 完整規格

```text
【Step 4 規格】

輸入：

- Step 3 通過的 symbol 清單

當前價格讀取順序：

- 5m → 1h → 4h → 1d（取第一個有資料的）

處理：

對每個 symbol：

【條件 1：1d 宏觀保障】

1. 讀最近 6 根 1d K 線
2. recent_1d_max_close = max(klines_1d[-6:-1].close)
3. current_price = get_current_price(symbol)（按上述順序）
4. 若 current_price <= recent_1d_max_close → 不通過
5. 計算 upper_wick 與 body
6. 若 upper_wick > body * 0.66 → 不通過

【條件 2：4h 核心動能】

1. 讀最近 6 根 4h K 線
2. min_low = min(klines.low)
3. max_high = max(klines.high)
4. rise_pct = (max_high - min_low) / min_low
5. 若 rise_pct < phase1_min_rise_pct（15%） → 不通過
6. 即時計算 4h RVOL
7. 若 max(rvol_4h) < phase1_4h_rvol_threshold（2.0） → 不通過

【條件 3：1h 爆發確認】

1. 讀最近 24 根 1h K 線
2. 找任一根同時滿足：
   - 即時計算 rvol_1h >= phase1_1h_rvol_threshold（3.0）
   - (close - open) / open >= phase1_1h_min_body_pct（0.5%）
3. 若找不到 → 不通過

【計算 previous_range_high_4h】

1. 找 origin_low 的時間戳（6 根 4h 中最低點）
2. 讀最近 50 根 4h K 線
3. 找到 origin_low 對應的索引
4. 往前推 30 根（約 5 天）
5. 取這段期間的 4h 最高收盤價 = previous_range_high_4h
6. 若樣本不足 30 根 → 用現有樣本
7. 若樣本 < 10 根 → 不通過 Step 4

【儲存 Phase 1 錨點】

寫入 Redis strategy:phase1:{symbol}：

- origin_low
- peak_high
- peak_timestamp_ms
- previous_range_high_4h
- phase1_detected_at
- phase1_4h_rise_pct
- phase1_1h_rvol

輸出：

`list[Phase1Result]`（canonical model 見 Chapter 9 §9.4.3）。本節只描述策略流程，不建立第二個輸出 schema。

參數（Telegram 可調）：

- phase1_1d_lookback_days: 5
- phase1_max_upper_wick_ratio: 0.66
- phase1_4h_lookback_bars: 6
- phase1_min_rise_pct: 15.0
- phase1_4h_rvol_threshold: 2.0
- phase1_1h_lookback_bars: 24
- phase1_1h_rvol_threshold: 3.0
- phase1_1h_min_body_pct: 0.5
- phase4_previous_range_lookback_bars: 30
- phase4_previous_range_min_bars: 10

錯誤處理：

- K 線不足 → 記錄 insufficient_klines，跳過
- ClickHouse 讀取失敗 → 記錄 clickhouse_read_failed，跳過
```

### 7.4.3 級別衝突處理

若只有 1d 放量，4h 與 1h 都沒放量：

| 條件                                | 動作   |
| ----------------------------------- | ------ |
| `upper_wick > body * 1.5`         | REJECT |
| `daily.close > daily.open * 1.05` | ACCEPT |
| 其他                                | REJECT |

### 7.4.4 條件 1「當前價格」的定義

依序查詢 ClickHouse，取第一個有資料的：

```text
5m → 1h → 4h → 1d
```

## 7.5 Step 5：Phase 2 回踩期

### 7.5.1 核心設計

**三層守門員**：

| Timeframe | 角色         | 檢查深度                     |
| --------- | ------------ | ---------------------------- |
| **1d**    | 大趨勢守門員 | 只檢查「有沒有破底」         |
| **4h**    | 結構守門員   | 只檢查「有沒有連續暴力倒貨」 |
| **1h**    | 主戰場       | 精確計算回撤幅度 + 縮量狀態  |

### 7.5.2 組合型判定（A+B+C）

| 方案                | 內容                  |
| ------------------- | --------------------- |
| **A. 回撤型** | 從高點回撤 5% ~ 20%   |
| **B. 未破型** | 現價 > Phase 1 起漲點 |
| **C. 縮量型** | 1h 陰線 RVOL < 2.5    |

### 7.5.3 完整規格

```text
【Step 5 規格】

輸入：

- Step 4 通過的 symbol 清單
- Redis strategy:phase1:{symbol}

處理：

對每個 symbol：

【條件 1：前置確認】

1. 讀 strategy:phase1:{symbol}
2. 若不存在 → 記錄 debug，跳過
3. 取出 origin_low、peak_high、peak_timestamp_ms、previous_range_high_4h
4. 若 now_ms() - peak_timestamp_ms > 48h → 記錄 debug，跳過

【守門員：1d】

1. 讀最近 4 根 1d K 線
2. min_low_3d = min(klines_1d[-4:-1].low)
3. 若 current_close < min_low_3d → 不通過

【守門員：4h】

1. 讀最近 4 根 4h K 線
2. dump_count = count(k.close < k.open and k.rvol_ma7 >= 2.0)
3. 若 dump_count >= 2 → 不通過

【主戰場：1h】

1. 讀最近 48 根 1h K 線
2. 條件 2：價格行為
   a. drawdown_pct = (peak_high - current_close) / peak_high * 100
   b. 若 drawdown_pct < 5.0 → 不通過
   c. 若 drawdown_pct > 20.0 → 不通過
   d. 若 current_close <= origin_low → 不通過
3. 條件 3：縮量檢查
   a. pullback_klines = [k for k in klines_1h if k.timestamp > peak_timestamp_ms]
   b. 對每根陰線（close < open）檢查 rvol_ma7
   c. 若有任一根 rvol_ma7 >= 2.5 → 不通過

【跌破 origin_low 立即清理】

若 current_close <= origin_low：
- DEL strategy:phase1:{symbol}
- SREM strategy:phase1:active {symbol}

輸出：

list[Phase2Candidate]：
  [
    {
      "symbol": "BTCUSDT",
      "phase2_confirmed": True,
      "peak_high": "3700.00",
      "origin_low": "3200.00",
      "previous_range_high_4h": "3500.00",
      "current_price": "3450.00",
      "drawdown_pct": 6.76,
      "peak_timestamp_ms": 1726800000000,
      "phase2_detected_at": 1726800000000,
    },
    ...
  ]

參數（Telegram 可調）：

- phase2_phase1_max_age_hours: 48
- phase2_min_drawdown_pct: 5.0
- phase2_max_drawdown_pct: 20.0
- phase2_max_dump_rvol: 2.5
- phase2_1d_break_lookback: 3
- phase2_4h_dump_count_max: 2
- phase2_4h_dump_rvol: 2.0

錯誤處理：

- Phase 1 數據不存在 → 記錄 debug，跳過
- K 線不足 → 記錄 insufficient_klines，跳過
- ClickHouse 讀取失敗 → 記錄 clickhouse_read_failed，跳過
```

### 7.5.4 Phase 1 數據的儲存（Redis）

| Key                          | 類型 | TTL                     | 用途                        |
| ---------------------------- | ---- | ----------------------- | --------------------------- |
| `strategy:phase1:{symbol}` | Hash | **172800（48h）** | 單一 symbol 的 Phase 1 錨點 |
| `strategy:phase1:active`   | Set  | 無                      | 所有 Phase 1 中的 symbol    |

 **`strategy:phase1:{symbol}` 結構** ：

```text
HSET strategy:phase1:BTCUSDT
  symbol                  BTCUSDT
  strategy_id             volume_breakout_pullback_v1
  origin_low              3200.00
  peak_high               3700.00
  peak_timestamp_ms       1726800000000
  previous_range_high_4h  3500.00
  phase1_detected_at      1726800000000
  phase1_4h_rise_pct      15.63
  phase1_1h_rvol          3.50
  updated_at              1726800000000
```

### 7.5.5 清理機制

| 情境              | 處理                        |
| ----------------- | --------------------------- |
| TTL 到期          | 自動移除                    |
| 跌破 origin_low   | 立即移除                    |
| 通過 Step 6       | 保留（進入 Step 7）         |
| 未通過且超過 48h  | 下次讀取時從 Set 移除       |


## 7.6 Step 6：接近低價區

### 7.6.1 核心設計

動態支撐區取代固定天數低價區：

| 支撐點     | 定義                          | 來源                       |
| ---------- | ----------------------------- | -------------------------- |
| S/R Flip   | Phase 1 突破前的那個天花板    | `previous_range_high_4h`   |
| Origin Low | Phase 1 這波上漲的最低點      | `origin_low`               |

### 7.6.2 完整規格

```text
【Step 6 規格】

輸入：

- Step 5 通過的 symbol 清單
- Redis strategy:phase1:{symbol}

處理：

對每個 symbol：

【檢查 A：S/R Flip 區（首選）】

1. support_target = previous_range_high_4h
2. upper = support_target * (1 + tolerance_pct / 100)
3. lower = max(
     support_target * (1 - tolerance_pct / 100),
     origin_low * (1 + origin_low_buffer_pct / 100),
   )
4. 若 lower <= current_price <= upper：
   → 通過，support_type = "S_R_FLIP"

【檢查 B：起漲點區（備用）】

1. support_target = origin_low
2. upper = support_target * (1 + tolerance_pct / 100)
3. lower = origin_low
4. 若 lower <= current_price <= upper：
   → 通過，support_type = "ORIGIN_LOW"

【中間地帶】

若價格在 A 區下方、B 區上方：
→ 不通過，reason = "no_mans_land"

輸出：

list[Candidate]：
  [
    {
      "symbol": "BTCUSDT",
      "timeframe_primary": "4h",
      "previous_range_high": "3500.00",
      "origin_low": "3200.00",
      "peak_high": "3700.00",
      "current_price": "3450.00",
      "phase2_detected_at_ms": 1726800000000,
      "support_type": "S_R_FLIP",
      "support_target_price": "3500.00",
      "drawdown_pct": 6.76,
    },
    ...
  ]

參數（Telegram 可調）：

- phase6_tolerance_pct: Decimal("3.0")（百分比點；公式內除以 100）
- phase6_origin_low_buffer_pct: Decimal("3.0")（百分比點；公式內除以 100）
- phase6_check_origin_low: true
- phase6_use_ma_confluence: false

錯誤處理：

- Phase 1 數據不存在 → 記錄 debug，跳過
- previous_range_high_4h 缺失 → 記錄 invalid_data，跳過
- K 線不足 → 記錄 insufficient_klines，跳過
```

### 7.6.3 關鍵決策

| 決策                 | 選擇                                 |
| -------------------- | ------------------------------------ |
| A 區與 B 區中間地帶  | **嚴格不接**                         |
| 1d 均線共振          | 預設關閉                             |
| 倉位區分             | 第一版不區分，只標記 `support_type`  |

---

## 7.7 Step 7：產生候選名單

### 7.7.1 核心任務

| 任務                 | 說明                     |
| -------------------- | ------------------------ |
| **標準化打包** | 產生`Candidate` |
| **全局去重**   | 冷卻機制                 |
| **模式分流**   | MANUAL / SEMI / AUTO     |

### 7.7.2 Candidate 結構（引用 Chapter 9 canonical model）

> 本章不再定義第二個 `Candidate` schema。唯一 canonical model 是 [Chapter 9 §9.4.1](BLUEPRINT-PART05-Chapter09-10-StrategyPluginInterface.md) 的 `Candidate`。本策略 Step 7 產生該模型；策略專屬欄位若不屬於共用欄位，放入 `Candidate.data`。`Candidate` 僅作舊文件名稱/遷移別名，不得作為新的 normative class。

| 本章策略欄位 | Canonical Candidate 欄位 |
|---|---|
| `symbol`、`strategy_id`、`trace_id`、`generated_at_ms` | 同名欄位 |
| `support_type`、`current_price`、`support_target_price` | 同名共用欄位 |
| `origin_low`、`peak_high`、`previous_range_high` | 同名共用欄位 |
| `drawdown_pct`、`profit_potential_pct` | 同名共用欄位 |
| 其他策略專屬資料 | `Candidate.data[...]` |

### 7.7.3 完整規格

```text
【Step 7 規格】

輸入：

- Step 6 通過的 Candidate 清單
- MariaDB strategies 表（mode 配置）

處理：

對每個 candidate：

【前置檢查】

1. 讀 strategy:cooldown:{symbol}
2. 若存在 → 記錄 debug，跳過
3. 若不存在 → 繼續

【產生 Candidate】

1. 產生 trace_id = uuid4()
2. 計算 profit_potential_pct = (peak_high - current_price) / current_price * 100
3. 若 profit_potential_pct < min_profit_potential_pct → 記錄 debug，跳過
4. 組裝 Candidate，初始狀態依 mode 設為 `PENDING_REVIEW`（SEMI/MANUAL）或 `AUTO_APPROVED`（AUTO）
5. 以 MariaDB `strategy_candidates` 作為 authoritative record；Redis pipeline/Lua 只建立對應熱狀態
6. 設定 cooldown（SET NX EX）

【依 mode 分流】

若 mode == "MANUAL"：

1. 寫入 MariaDB `strategy_candidates`（status=PENDING_REVIEW）
2. Pipeline/Lua 寫入 Redis `strategy:candidate_data` 與 `telegram:message_map`
3. 不寫 `strategy:pending_reviews` 或 `strategy:pending_review:active`
4. 發送 Telegram 訊息（含 [手動進場] 按鈕，無逾時）
4. 通知後結束（無逾時，使用者可隨時手動進場
5. 【新增】使用者點擊「手動進場」時，執行價格保護檢查（見 8.4.3）

若 mode == "SEMI"：

1. 寫入 MariaDB `strategy_candidates`（status=PENDING_REVIEW）
2. Redis Pipeline/Lua 同步寫入 `strategy:candidate_data`、`strategy:pending_reviews`、`strategy:pending_review:active`
3. ZSET score = `expire_at_ms`（UTC 13 位毫秒）
4. 發送 Telegram 訊息（含 Inline Keyboard）
6. 等待回應（10 分鐘逾時）

若 mode == "AUTO"：

1. 寫入 MariaDB strategy_candidates
2. status = AUTO_APPROVED
3. 直接呼叫 execute_step8_pricing(candidate)
4. 發送 Telegram 通知

【超時輪詢】（每 30 秒執行；只處理 SEMI ZSET）

1. expired = ZRANGEBYSCORE strategy:pending_reviews 0 {context.now_ms()}
2. 每個 expired trace_id 先取得 `lock:candidate:review:{trace_id}`（TTL 10s）
3. 鎖內再次 SISMEMBER `strategy:pending_review:active`；不存在即跳過
4. 依唯一正式 timeout 行為轉為 `AUTO_APPROVED`/MariaDB `TIMEOUT_AUTO`，執行 Step 8
5. Redis Pipeline/Lua 原子 ZREM + SREM + HDEL；MariaDB terminal update 必須成功
6. 發送 Telegram High 通知；通知失敗進入 buffer，不回滾業務狀態

輸出：

list[Candidate]

參數（Telegram 可調）：

- min_profit_potential_pct: 10.0
- cooldown_hours: 24
- semi_timeout_minutes: 10
- timeout_action: AUTO
- review_poll_interval_sec: 30

錯誤處理：

- Redis 讀取失敗 → 記錄 warning，跳過
- MariaDB 讀取失敗 → 用預設 mode（SEMI）
- Telegram 發送失敗 → 記錄 error，保留 candidate
```

**Candidate lifecycle contract：**

- Candidate terminal status 只可由 MariaDB `strategy_candidates.status` 確認：`CONFIRMED`、`REJECTED`、`MANUAL_PRICE_DEVIATION_REJECT`、`TIMEOUT_AUTO`、`TIMEOUT_CANCEL`。
- Redis TTL 到期不代表 terminal；reconciliation 必須找出 MariaDB 仍為非 terminal 但 Redis 缺失的 Candidate。
- Confirm/Reject/Timeout 共用 `lock:candidate:review:{trace_id}`；取得鎖後檢查 active Set，再以 Pipeline/Lua 原子清理。
- Confirm 只在 PENDING_REVIEW（或 MANUAL 手動觀察流程）合法；custom_tp 只在 Confirm → Step 8 時 Decimal 驗證並鎖定。
- MANUAL 永不進入 pending review ZSET；Telegram 通知失敗不影響已持久化的 Candidate，改由 `telegram:buffer:{tg_id}` 緩衝。



| Key                                | 類型   | TTL | 用途                       |
| ---------------------------------- | ------ | --- | -------------------------- |
| `strategy:cooldown:{symbol}`     | String | 24h | 冷卻標記                   |
| `strategy:cooldown:active`       | Set    | 無  | 所有冷卻中 symbol          |
| `strategy:pending_reviews`       | ZSET   | 無  | Score = 過期時間戳         |
| `strategy:candidate_data`        | Hash   | 7d  | trace_id → Candidate JSON |
| `strategy:pending_review:active` | Set    | 無  | 待審核 trace_id            |

### 7.7.5 三種模式的 Telegram 訊息

**SEMI**：

```text
🚨 *策略觸發：Volume Breakout Pullback* 🚨
幣種：`BTCUSDT`
支撐類型：`S_R_FLIP`
觸發市價：`$65,120`
📉 *防守底線*：`$63,000`
📈 *預設停利*：`$71,500`
💰 *資金權重*：10%
⏳ *審核倒數*：10 分鐘
💡 若要自訂停利價，請直接「回覆」本訊息並輸入數字
[✅ 一鍵預設進場] [❌ 拒絕並冷卻] [📊 查看圖表] [ℹ️ 詳情]
```

**MANUAL**：

```text
📢 *策略觀察：Volume Breakout Pullback* 📢
...
ℹ️ *無逾時限制，您可隨時手動進場*
[🖐️ 手動進場] [❌ 拒絕並冷卻] [📊 查看圖表] [ℹ️ 詳情]
```

**AUTO**：

```text
🤖 *自動進場觸發*
...
系統將自動計算掛單價並下單。
```

### 7.7.6 自訂停利（Telegram Reply）

 **Redis 映射** ：

| Key                      | 類型 | TTL | 用途                   |
| ------------------------ | ---- | --- | ---------------------- |
| `telegram:message_map` | Hash | 7d  | message_id → trace_id |

 **流程** ：

1. `ccurr-telegram` 發送 Step 7 訊息時，將 `message_id → trace_id` 寫入
2. 使用者回覆訊息並輸入數字
3. `ccurr-telegram` 讀取 `reply_to_message.message_id`，查映射得 `trace_id`
4. 呼叫 `ccurr-strategy` UDS `POST /candidate/confirm` 帶 `custom_tp`

---

## 7.8 Step 8：計算掛單價 + OTOCO

### 7.8.1 Signal 結構（引用 Chapter 9 canonical model）

> 本章不再定義第二個 `Signal` schema。唯一 canonical model 是 [Chapter 9 §9.4.2](BLUEPRINT-PART05-Chapter09-10-StrategyPluginInterface.md) 的 `Signal`；本節的交易計畫與 metadata 只是該模型的業務使用範例。欄位命名、Decimal 規則與 live/backtest 共用的 `OrderIntent` 由 Chapter 9 §9.4.3 規範。

> **Spot Order Intent**：`Signal.plan` 只表達策略意圖；`pending_quantity`、Spot filters、clientOrderId 與 Binance REST 參數由 executor/risk/trader adapter 依 Chapter 6/9 契約補齊。策略不直接呼叫 Binance。

### 7.8.2 完整規格

```text
【Step 8 規格】

輸入：

- Step 7 通過的 Candidate
- 可選 custom_tp
- runtime_config

處理：

對每個 candidate：

【1. 計算進場價】

1. entry_price = support_target_price * (1 + entry_offset_pct / 100)
2. entry_type = "LIMIT"（永遠不用 MARKET）
3. entry_price_final = entry_price

註：即使現價已低於 entry_price，仍掛 LIMIT。
撮合引擎會以最優市價成交。

【2. 計算停損價】

1. stop_price = origin_low * (1 - stop_loss_buffer_pct / 100)
2. stop_limit_price = stop_price * (1 - stop_limit_buffer_pct / 100)

【3. 計算停利價】

1. 若 custom_tp 提供：
   - take_profit_price = custom_tp
   - is_custom = True
   否則：
   - take_profit_price = peak_high * (1 - take_profit_buffer_pct / 100)
   - is_custom = False

【4. 計算資金權重】

1. 依 support_type：
   - S_R_FLIP → weight_sr_flip（10.0）
   - ORIGIN_LOW → weight_origin_low（5.0）
   - 其他 → weight_fallback（1.0）

【5. 打包 Signal】

1. signalId = uuid4()
2. traceId = candidate.trace_id
3. plan = {entry, take_profit, stop_loss}
4. weight_pct
5. metadata

【6. 發布 Signal】

1. publish("signal:all", signal.model_dump())

輸出：

Signal（已發布到 Redis）

參數（Telegram 可調）：

- entry_offset_pct: Decimal("1.0")（百分比點）
- stop_loss_buffer_pct: Decimal("1.0")（百分比點；V1 canonical，統一 1.0%，不分級）
- stop_limit_buffer_pct: Decimal("1.0")（百分比點）
- take_profit_buffer_pct: Decimal("0.5")（百分比點）
- weight_sr_flip: Decimal("10.0")（百分比點）
- weight_origin_low: Decimal("5.0")（百分比點）
- weight_fallback: Decimal("1.0")（百分比點）
- strategy_allocation_pct: Decimal("20.0")（百分比點）
- entry_timeout_hours: 4

錯誤處理：

- 當前價讀取失敗 → 記錄 warning，跳過
- custom_tp 不合理 → 拒絕，回報使用者
- Signal 發布失敗 → 記錄 error，重試
```

### 7.8.3 幣安 OTOCO 支援

OTOCO：Entry + TP + SL 三合一。

執行流程：

```text
1. ccurr-executor 收到 Signal
2. 優先嘗試 POST /order/otoco
3. 若幣安回 Not Supported：
   - Fallback：送 Entry LIMIT 單
   - 寫入 order:pending_oco:{entry_order_id}
   - 交由 ccurr-order 在 Entry FILLED 時補送 OCO
```

### 7.8.4 三個關鍵修正

| 修正              | 內容                                                                   |
| ----------------- | ---------------------------------------------------------------------- |
| Entry 永遠 LIMIT  | OTOCO 不支援 MARKET，掛高價 LIMIT 讓撮合引擎以最優市價成交             |
| Fallback 狀態機   | 不用 `await wait_for_fill`，寫 `pending_oco` 標記交給 `ccurr-order`    |
| V1 停損緩衝 | `stop_loss_buffer_pct = 1.0%` 統一、不分級；0.2/0.5/2.0 tier 僅 future/non-active |

### 7.8.5 ccurr-risk R17/R06/R12/R14/R13 規則（V1）

```text
1. Step 8 先決定 entry_price、stop_price、stop_limit_price
2. R17 以 strategy_allocation_pct + Capital Allocation weight_pct 計算 original_R17_qty
3. R06 以停損距離、雙向費用及 total_account_value 作最高優先風險否決
4. final_qty = min(original_R17_qty, risk_based_qty)
5. R12 對 final_qty 依 stepSize 向下截斷
6. 截斷後重新驗證 R14 minQty/minNotional；不足一律 DENY，不向上放大
7. R13 以 entry_price × qty × (1 + fee_rate) 檢查 balance:USDT.free
8. 通過後才由 ccurr-risk 將 calculated_qty 附加至 Signal/OrderIntent
```

`weight_pct` V1 代表資金權重（S_R_FLIP=10.0、ORIGIN_LOW=5.0），不是風險權重。R06 的 `max_risk_per_trade_pct` 預設 2.0% 優先於策略 allocation。Live 與 Backtest 必須消費同一 RiskCalculator 商業契約；S6 Risk-Parity 僅是未來版本。

## 7.9 Step 9：掛單超時管理

### 7.9.1 核心設計

由 ccurr-order 的 TimeoutLoop 負責。

ZSET 延遲佇列：

| Key                 | 類型 | 用途                                       |
| ------------------- | ---- | ------------------------------------------ |
| order:timeout_queue | ZSET | Score = 超時時間戳，Member = clientOrderId |

### 7.9.2 完整規格

```text
【Step 9 規格】

輸入：

- Redis order:timeout_queue（ZSET）
- Redis order:pending:*

處理：

ccurr-order 的 TimeoutLoop（每 60 秒）：

【1. 抓出超時訂單】

1. now = now_ms()   # 13 位毫秒整數
2. expired = ZRANGEBYSCORE order:timeout_queue 0 {now}
3. 若 expired 為空 → 結束

【2. 對每個超時訂單】

for clientOrderId in expired:
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

參數（Telegram 可調）：

- timeout_hours_a_zone: 24
- timeout_hours_b_zone: 48
- timeout_check_interval_sec: 60
- cancel_retry_max: 3
- cancel_retry_backoff_sec: 2.0

錯誤處理：

- Redis 讀取失敗 → 記錄 warning，跳過
- CANCEL 失敗 → 重試 3 次，仍失敗發 critical 告警
- OCO 補送失敗 → 發 critical 告警，保留 pending_oco 標記
```

### 7.9.3 部分成交處理

| 情境                 | 動作                                 |
| -------------------- | ------------------------------------ |
| `NEW`              | 直接取消                             |
| `PARTIALLY_FILLED` | 取消剩餘 + 用`executedQty`補送 OCO |
| `FILLED`           | 什麼都不做，讓 OCO 繼續運作          |

### 7.9.4 關鍵決策

| 決策                              | 選擇                                      |
| --------------------------------- | ----------------------------------------- |
| V1 策略                           | 絕對取消（不改價、不延長）                |
| 超時後清理                        | 保留`order:pending:*`（TTL 7 天）供審計 |
| 超時後重新觸發 Step 1~7           | 不觸發                                    |
| `timeout_hours`依`weight_pct` | 不調整                                    |

### 7.9.5 `order:pending:*` 結構

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

## 7.10 參數總表

### 7.10.1 Step 1~3

```python
{
    # Step 1
    "symbol_cache_ttl_sec": 300,
    "blacklist_cache_ttl_sec": 300,

    # Step 2
    "scan_interval_sec": 900,
    "threshold_ma7": Decimal("3.0"),
    "threshold_ma20": Decimal("2.0"),
    "min_elapsed_min_1d": 30,  # 讀取後轉為 elapsed_ms
    "min_samples_7d": 5,
    "min_samples_20d": 15,

    # Step 3
    "min_volume_24h_usdt": 3000000,
    "volume_check_lookback_4h": 6,
    "min_volume_samples": 4,
}
```

### 7.10.2 Step 4~6

```python
{
    # Step 4
    "phase1_1d_lookback_days": 5,
    "phase1_max_upper_wick_ratio": Decimal("0.66"),
    "phase1_4h_lookback_bars": 6,
    "phase1_min_rise_pct": Decimal("15.0"),
    "phase1_4h_rvol_threshold": Decimal("2.0"),
    "phase1_1h_lookback_bars": 24,
    "phase1_1h_rvol_threshold": Decimal("3.0"),
    "phase1_1h_min_body_pct": Decimal("0.5"),
    "phase4_previous_range_lookback_bars": 30,
    "phase4_previous_range_min_bars": 10,

    # Step 5
    "phase2_phase1_max_age_hours": 48,
    "phase2_min_drawdown_pct": Decimal("5.0"),
    "phase2_max_drawdown_pct": Decimal("20.0"),
    "phase2_max_dump_rvol": Decimal("2.5"),
    "phase2_1d_break_lookback": 3,
    "phase2_4h_dump_count_max": 2,
    "phase2_4h_dump_rvol": Decimal("2.0"),

    # Step 6
    "phase6_tolerance_pct": Decimal("3.0"),
    "phase6_origin_low_buffer_pct": Decimal("3.0"),
    "phase6_check_origin_low": True,
    "phase6_use_ma_confluence": False,
    "phase6_ma_confluence_tolerance_pct": Decimal("1.0"),
}
```

### 7.10.3 Step 7~9

```python
{
    # Step 7
    "min_profit_potential_pct": Decimal("10.0"),
    "cooldown_hours": 24,
    "semi_timeout_minutes": 10,
    "timeout_action": "AUTO",
    "review_poll_interval_sec": 30,
    "manual_entry_max_deviation_pct": Decimal("1.0"),  # 百分比點

    # Step 8
    "entry_offset_pct": Decimal("1.0"),
    "stop_loss_buffer_pct": Decimal("1.0"),  # V1 canonical; no tiers
    "stop_limit_buffer_pct": Decimal("1.0"),
    "stop_limit_buffer_pct_by_tier": {
        "large": 0.2,
        "medium": 0.5,
        "small": 2.0,
    },
    "take_profit_buffer_pct": Decimal("0.5"),
    "weight_sr_flip": Decimal("10.0"),
    "weight_origin_low": Decimal("5.0"),
    "weight_fallback": Decimal("1.0"),
    "strategy_allocation_pct": Decimal("20.0"),
    "entry_timeout_hours": 4,
    "prefer_otoco": True,
    "pending_oco_ttl_sec": 604800,
    "allow_custom_tp": True,
    "custom_tp_min_multiplier": 1.01,
    "custom_tp_max_multiplier": 10.0,

    # Step 9
    "timeout_hours_a_zone": 24,
    "timeout_hours_b_zone": 48,
    "timeout_check_interval_sec": 60,
    "cancel_retry_max": 3,
    "cancel_retry_backoff_sec": 2.0,
}
```

## 7.11 完整流程範例

### 7.11.1 情境：SEMI 模式 + 一鍵預設進場

```text
T=0s（Step 1~6 掃描）：
  • 320 個 symbol → 15 個放量 → 8 個成交額達標
  • 3 個通過 Phase 1
  • 2 個通過 Phase 2
  • 1 個通過 Step 6（BTCUSDT）

T=0.1s（Step 7）：
  • 產生 Candidate
  • trace_id = uuid-v4
  • status = PENDING_REVIEW
  • ZADD strategy:pending_reviews {T+10min} {trace_id}
  • HSET telegram:message_map {message_id} {trace_id}
  • 發送 Telegram（含 Inline Keyboard）

T=30s（使用者點擊「一鍵預設進場」）：
  • ccurr-telegram 收到 callback
  • 檢查 ZSET → trace_id 還在 pending
  • 呼叫 ccurr-strategy UDS: POST /candidate/confirm
    {trace_id, action: "CONFIRM"}

T=30.1s（Step 8）：
  1. entry_price = 65000 * 1.01 = 65650
  2. entry_type = "LIMIT"（不用 MARKET）
  3. stop_price = 63000 * 0.995 = 62685
     stop_limit_price = 62685 * 0.99 = 62058.15
  4. take_profit_price = 71500 * 0.995 = 71142.50
  5. weight_pct = 10.0（S_R_FLIP）
  6. 打包 Signal 發布到 signal:all

T=30.2s（ccurr-executor）：
  1. 降級檢查 → 通過
  2. 呼叫 ccurr-risk
  3. ccurr-risk 執行 R17：
     - 帳戶總值 = $10,000
     - strategy_allocation_pct = 20% → $2,000
     - weight_pct = 10% → $200
     - qty = $200 / $65,120 = 0.00307 BTC
  4. R06 檢查通過
  5. 回傳 {allowed: true, calculated_qty: 0.00307}

T=30.3s（OTOCO）：
  POST /order/otoco {
    entry: {type: LIMIT, price: 65650, qty: 0.00307},
    tp: {price: 71142.50},
    sl: {stop_price: 62685, stop_limit_price: 62058.15},
  }

T=30.5s（幣安回應）：
  {orderListId: 123, status: NEW}
  → Entry 立即成交（撮合引擎以 $65,120 成交）
  → 幣安自動掛出 OCO

T=31s（ccurr-order 追蹤）：
  • 查詢 orderList 狀態
  • Entry FILLED，TP/SL WORKING
  • 更新 position:BTCUSDT
  • 發 position:updated 事件
```

### 7.11.2 情境：超時取消（部分成交）

```text
T=0s：
  Entry LIMIT 單送出（B 區，48h 超時）
  ZADD order:timeout_queue {T+48h} {clientOrderId}

T=24h：
  部分成交 30%（executed_qty=0.000921）
  status = PARTIALLY_FILLED

T=48h（TimeoutLoop）：
  1. ZRANGEBYSCORE → [clientOrderId]
  2. 讀 order:pending → status=PARTIALLY_FILLED
  3. 送 CANCEL → 成功
  4. HSET status=TIMEOUT_CANCELED
  5. executed_qty=0.000921 > 0
  6. 檢查 order:pending_oco:{clientOrderId}
     → 存在
  7. 用 executed_qty 補送 OCO
  8. 若 OCO 回應成功 → DEL order:pending_oco:{clientOrderId}
     若 OCO 失敗/逾時 → 保留 pending_oco、遞增 retry_count、發告警
  9. 發事件 + Telegram 通知
  10. ZREM order:timeout_queue {clientOrderId}
```

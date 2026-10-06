# Findings & Decisions

## Requirements
- 審查專案內所有藍圖，回報可證實的錯誤；每項標示檔案、章、節、錯誤內容與影響。
- 不修改藍圖正文。

## Research Findings
- 藍圖由 `BLUEPRINT-PART01` 至 `PART06` 分檔，另有 `BLUEPRINT-CCURR-MASTER.md` 目錄與 `blueprint-v4-01.md` 摘要；合計約 12,772 行。
- `BLUEPRINT-PART05-Chapter07-07-StrategyStep1-9.md` 7.8.2/7.10.3 將 `stop_loss_buffer_pct` 設為 0.5%；`BLUEPRINT-PART06-Chapter12-12-TodoAndOpenIssues.md` 12.2.2 B5 仍寫「停損緩衝 0.5%」，但 12.3.2 D7 建議及 12.3.3 最終決策改為統一 1.0%。這是未同步的參數衝突。
- Chapter 6 §6.7.7 的 Binance OTO 參數表同時以「OTOCO」稱呼流程；其 fallback 在 6.7.9 卻是 Entry + 後送 OCO，術語/模型需要明確區分 OTO 與 OTOCO，否則實作者可能呼叫錯誤 API/訂單模型。
- Chapter 7 §7.8.2 的 R17 先以固定金額/價格計算 qty（7.8.5），再聲稱檢查 R06 單筆最大風險；但公式未使用 stop distance/stop loss，無法保證實際停損損失不超過 `max_risk_per_trade_pct`（Chapter 3 §3.2.9）。這是風控契約缺口，不只是命名問題。
- Chapter 12 §12.1.3 宣稱 MariaDB 20 張表；Chapter 2 §3.2 實際列出 14 組小節但包含成對/三張表，需重新核對實際 CREATE TABLE 總數，否則「20 張」沒有可驗證來源。
- `blueprint-v4-01.md` 不是 v4 master 的完整內容，而是短版摘要；其中仍把 D7/停損緩衝描述成 0.5%（A/B 假設與摘要），與已確認 1.0% 不一致。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 只列出能從藍圖文字直接證明的問題 | 避免把需查官方 API 或實測才能確認的事項誤報成錯誤 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| `resolve-plan-dir.sh` 被 Python 誤執行，回傳 SyntaxError | 改用 `sh` 執行；成功建立並使用 `.planning/2026-10-02-blueprint-audit/` |
| 專案不是 Git repository | 不進行 git diff；記錄為環境限制 |

## Resources
- `BLUEPRINT-PART01-Chapter00-02-SystemOverview.md`
- `BLUEPRINT-PART02-Chapter03-04-DataLayer.md`
- `BLUEPRINT-PART04-Chapter06-06-Container.md`
- `BLUEPRINT-PART05-Chapter07-07-StrategyStep1-9.md`
- `BLUEPRINT-PART05-Chapter08-08-StrategyEngine.md`
- `BLUEPRINT-PART05-Chapter09-10-StrategyPluginInterface.md`
- `BLUEPRINT-PART06-Chapter11-11-AIGenerationOrder.md`
- `BLUEPRINT-PART06-Chapter12-12-TodoAndOpenIssues.md`

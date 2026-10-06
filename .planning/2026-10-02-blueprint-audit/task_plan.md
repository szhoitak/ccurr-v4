# Task Plan: Blueprint audit

## Goal
完成所有專案藍圖的靜態一致性與可實作性審查，向使用者列出每個已證實錯誤的章節、節次、證據、影響與修正方向；不修改藍圖正文。

## Next Step
待可執行 Python runtime/test source 恢復或建立後，依 `BLUEPRINT-G3-LOCAL-TEST-PLAN.md` 實作並執行 local-only evidence；目前不生成 production code。

## Current Phase
Phase 4

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints
- [x] Document in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Define approach
- [x] Create project structure
- **Status:** complete

### Phase 3: Implementation
- [x] Execute the plan
- [x] Write to files before executing
- **Status:** complete (audit only; no blueprint edits)

### Phase 4: Testing & Verification
- [x] Verify requirements met
- [x] Document test results
- **Status:** in_progress

### Phase 5: Delivery
- [ ] Review outputs
- [ ] Deliver to user
- **Status:** pending

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 只報告可由藍圖內文直接證明的錯誤 | 避免將需實測或查外部官方文件的假設誤列為確定錯誤 |
| 以章/節為主、附檔案與行號 | 使用者要求能定位問題，分檔藍圖需要檔名避免歧義 |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| `resolve-plan-dir.sh` 被 Python 執行造成 SyntaxError | 改以 `sh` 執行，成功解析規劃目錄 |
| 專案不是 Git repository，`git diff --stat` 回傳 129 | 視為環境限制；改用檔案與全文搜尋審查 |

# NOT_PROVEN Acceptance Matrix — 2026-10-05

## Purpose

將目前 G3/G4 尚未證明的項目轉成可驗收 wording。這些是 acceptance gates，不是完成聲明；所有項目目前狀態為 `NOT_PROVEN`。

| ID | Area | Acceptance wording | Evidence required |
|---|---|---|---|
| NP01 | StrategyEngine/plugin loader | Container/service loads the registered strategy by canonical id; duplicate/unknown plugin behavior is deterministic; constructor/lifecycle test passes in live and backtest adapters. | executable service/loader tests, source hash, isolated logs |
| NP02 | DB/Redis adapters | Decimal/UTC epoch-ms payloads round-trip through the approved adapters without float coercion; MariaDB terminal Candidate status remains authoritative after Redis TTL cleanup/reconciliation. | adapter round-trip tests, reconciliation test, no live data mutation in local run |
| NP03 | Exchange transport | Approved trader boundary returns correlated success/error responses; retry reuses clientOrderId; UNKNOWN is queried before retry; no blind duplicate order. | fake transport contract first, then explicitly authorized sandbox evidence |
| NP04 | Partial-fill OCO | Given executed_qty and fee mode, safe OCO quantity is quantized down and rejected below minQty/minNotional; failed placement retains pending state; successful placement consumes it. | deterministic fake broker tests plus approved adapter response evidence |
| NP05 | Distributed race | Confirm/timeout across multiple workers uses the same lock and atomic cleanup; exactly one winner executes Step 8; duplicate callbacks are idempotent. | multi-worker/race test with controlled Redis double, then operational evidence if required |
| NP06 | Restart recovery | After restart, Candidate/order/pending-OCO snapshots restore without changing clientOrderId; UNKNOWN remains blocked until query/reconciliation; OPEN stays DENY until all readiness gates complete. | deterministic snapshot tests plus authorized service restart evidence |
| NP07 | Compose/profile isolation | Live/backtest profiles, sockets, macvlan, secrets, volumes, healthchecks and dependencies match the C07 contract; backtest cannot access live DB/Redis/dbwriter/network paths. | static compose validation plus authorized sandbox/container evidence |
| NP08 | Live/backtest service parity | Equivalent inputs produce equivalent constructor/lifecycle, Decimal rounding, RiskCalculator results, rejection metadata, order semantics and metrics in both services. | executable parity suite and recorded fixture/output comparison |
| NP09 | OCO same-bar priority | Normative TP-versus-SL priority is explicitly selected, documented, and tested for dual-trigger bars; no ambiguous result is silently chosen. | approved decision + deterministic dual-trigger test |
| NP10 | Reporting/calibration | Sharpe annualization, drawdown, profit factor, holding-time semantics and JSON/HTML reports match accepted reference fixtures; parameter sweep isolates failures. | reference dataset, analyzer tests, report artifact comparison |
| NP11 | Readiness/fault matrix | Redis/dbwriter/trader/accountsync/websocket degradation maps to the documented DENY/retry/fallback/buffer policy; OPEN predicate is observable and fail-closed. | state-machine tests plus authorized healthcheck/runtime evidence |

## Global acceptance rule

A row is `PASS` only when the exact evidence listed is captured. Blueprint text, static search, or an in-memory double alone may be `PARTIAL PASS` but cannot promote G3/G4. Until all required rows are accepted, release remains `INTEGRATION / NOT_RELEASED` and production generation is blocked.

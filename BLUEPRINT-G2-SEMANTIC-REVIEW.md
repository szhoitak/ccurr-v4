# G2 Semantic Review Record — 2026-10-04

## Scope and method

本記錄對目前 Blueprint 的 C01–C07 與 I01–I15 做文件層級 cross-contract semantic review。證據來源為 manifest、contract index、Chapter 1/3–12 與 schema inventory。這是人工/文件核對，不是 runtime、API、parity、race、recovery 或 deployment 測試；因此不會把 G3/G4 提升為 VERIFIED。

## Invariant checklist

| ID | Semantic check | Documentation result | Evidence / caveat |
|---|---|---|---|
| I01 | Strategy/Step only use injected Clock/StrategyContext | PASS (documentation scope) | Chapter 9 lifecycle/Clock contract; Chapter 8 summaries reference it. SystemClock illustration is a lower-level provider, not a strategy bypass. |
| I02 | UTC epoch-ms timestamps | PASS (documentation scope) | Chapter 1 global rule, Chapter 9 models, DB adapter mapping. |
| I03 | Canonical numeric models use Decimal | PASS (documentation scope) | Chapter 1/9 canonical model rules; remaining float/list examples are classified reference or forbidden-pattern checks. |
| I04 | Live/backtest same constructor/lifecycle | PASS (documentation scope) | Chapter 9 shared constructor/lifecycle and Chapter 10 adapter boundary. Runtime parity remains G3. |
| I05 | Spot-only; reduceOnly forbidden | PASS (documentation scope) | Chapter 6/9 OrderIntent; retained `reduceOnly` occurrences are prohibition/legacy warning text. |
| I06 | Retry reuses clientOrderId | PASS (documentation scope) | Chapter 6/9 order identity and retry rules. Runtime idempotency remains G3. |
| I07 | Pending OCO retained until successful placement | PASS (documentation scope) | Chapter 6/7/9 and corrected Chapter 7 example; failure retains state/retry/alert. |
| I08 | MariaDB owns Candidate terminal truth; Redis TTL is cleanup | PASS (documentation scope) | Chapter 7/9/12 lifecycle and recovery rules. |
| I09 | Risk order R17 → R06 → R12 → R14 → R13; R06 can veto | PASS (documentation scope) | Chapter 6 canonical risk contract, Chapter 7 usage, Chapter 9 RiskCalculator, Chapter 12 acceptance table. |
| I10 | Private/trading Binance APIs route via ccurr-trader | PASS (documentation scope) | Chapter 1/4/6 routing matrix; no active exception identified. Runtime routing remains G4/G3 evidence. |
| I11 | DB writes route via ccurr-dbwriter | PASS (documentation scope) | Chapter 1/3/4/6 boundary; documented offline backtest output is explicit exception. |
| I12 | One primary Redis writer per canonical key | PASS (documentation scope) | `price:latest` is websocket-only; trace keys are explicitly append-only telemetry exception; pending-order ownership is executor-create/order-update/terminate/recovery; position correction remains the only business-state write-through exception. |
| I13 | Reliable events backed by state/DB/reconciliation | PASS (documentation scope) | Chapter 3/5/6 recovery and event reliability matrix; Pub/Sub is not sole recovery source. |
| I14 | OPEN denied until readiness/reconciliation gates pass | PASS (documentation scope) | Chapter 6 predicate now explicitly includes infrastructure health, account.synced, order UNKNOWN handling, and pending-OCO recovery. |
| I15 | Backtest isolated from live sockets/macvlan/secrets/Redis/dbwriter | PASS (documentation scope) | Backtest writes only `/app/results`; it does not connect to dbwriter or live DB write path. |


## Cross-contract findings

### Resolved/documented

1. Chapter 9 is the sole strategy plugin/model/lifecycle authority; Chapters 7/8/10 are scoped as business rules, orchestration, and backtest implementation/reference.
2. Chapter 10 MockBroker pending-OCO flow now uses public `register_pending_oco`, `has_pending_oco`, and `pop_pending_oco`; `_pending_ocos` is implementation detail only.
3. OTO/OTOCO and fallback semantics are explicitly separated: atomic OTOCO versus `Entry + post-fill OCO`; partial fill uses `executed_qty` and does not activate pending order.
4. R17/R06/R12/R14/R13 order, fee handling, min-notional rejection, and live/backtest calculator sharing are documented as one contract.
5. Candidate MANUAL/SEMI/AUTO routing, MariaDB terminal authority, Redis TTL non-terminal semantics, and shared confirm/timeout lock are documented consistently.
6. Data authority, private API routing, DB writer boundary, reliable-event recovery, readiness denial, and backtest isolation are represented in the integrated invariants.

### Remaining evidence gaps (not documentation contradictions)

- No runtime/API contract tests.
- No model serialization/Decimal/time tests.
- No RiskCalculator live/backtest parity tests.
- No confirm/timeout race or partial-fill OCO tests.
- No restart/recovery tests.
- No deployment/readiness or actual routing verification.

### Resolved semantic blockers

1. **I12 / writer ownership:** `price:latest` is websocket-only; trace keys are explicitly append-only telemetry and excluded from canonical business-state writer rules; pending order/OCO ownership is executor-create and order-update/terminate/recovery.
2. **I14 / readiness predicate:** Chapter 6 now names infrastructure readiness, account reconciliation/`account.synced`, UNKNOWN order handling, and pending-OCO recovery as OPEN prerequisites.
3. **I15 / backtest result boundary:** backtest writes JSON/HTML only to `/app/results`, does not connect to dbwriter or live DB write paths, and any future DB export is a separately authorized offline exporter.

The previous five blockers are resolved at documentation level. Runtime routing, recovery, and isolation remain G3/G4 evidence scope.

## G2 conclusion

`G2 = VERIFIED (documentation scope)`.


## Safety boundary

No Python, Docker, Redis, MariaDB, Binance, remote host, service restart, deployment, formal queue, or real-trading operation was executed.

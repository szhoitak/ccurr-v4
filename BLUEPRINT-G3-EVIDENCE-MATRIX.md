# G3 Evidence Matrix — Local-only readiness

**Date:** 2026-10-05  
**Scope:** Blueprint-defined G3 evidence readiness plus the executed minimum runtime slice. Full G3 remains incomplete.

## Status vocabulary

- `PLANNED`: required by the Blueprint, test design not yet implemented.
- `IMPLEMENTATION_NOT_PRESENT`: required runtime/test subject is absent from this workspace.
- `NOT_RUN`: test exists or is planned, but no execution result is recorded.
- `PASS`/`FAIL`: reserved for captured local-only execution evidence; none may be inferred from Blueprint text.

## Evidence matrix

| Evidence area | Contract / invariants | Required local-only evidence | Fixtures / doubles | Current status |
|---|---|---|---|---|
| Constructor and lifecycle | C01 / I04 | identical live/backtest constructor, ContextBuilder, `on_start → scan/evaluate → on_stop` | fake context builders, deterministic strategy | PARTIAL PASS — in-memory lifecycle/parity tests in `G3-EVIDENCE-LOCAL.md`; full plugin loader/engine remains open |
| Model/API contract | C01/C03/C04/C05 / I05/I08/I09 | field validation, Spot-only OrderIntent, Candidate transitions, RiskResult schema | pure in-memory models | PARTIAL PASS — Phase 1 kernel models and tests in `G3-EVIDENCE-LOCAL.md`; service state machine remains NOT_PROVEN |
| Decimal and wire serialization | C02 / I02/I03 | Decimal JSON/Redis round-trip, no float coercion, UTC 13-digit epoch-ms | serializer and in-memory payloads | PARTIAL PASS — Phase 1 wire/Decimal tests in `G3-EVIDENCE-LOCAL.md`; DB/Redis adapter round-trip remains NOT_PROVEN |
| Injected clock | C01/C02 / I01/I02 | VirtualClock advance/reset, strategy/Step time delegation, no direct wall-clock path | VirtualClock/FakeClock | PARTIAL PASS — `G3-EVIDENCE-LOCAL.md` |
| Step 2 boundaries | C02 | zero denominator, NULL/missing volume, missing/duplicate slot, insufficient samples, open slot, threshold equality | offline historical data provider | PARTIAL PASS — typed offline fixture/provider/parity tests in `G3-EVIDENCE-LOCAL.md`; production historical adapter/live parity remains open |
| Order identity and retry | C03 / I05/I06 | Spot request shape, `reduceOnly` rejection, stable clientOrderId across retry | fake trader/exchange adapter | PARTIAL PASS — `G3-EVIDENCE-LOCAL.md`; deterministic retry identity only, no exchange transport |
| Pending OCO and partial fill | C03 / I07 | retain pending state until success; safe quantity from executed_qty; partial-fill fallback | MockBroker, fake filters/fees | PARTIAL PASS — safe quantity/state-machine tests; full exchange response/runtime parity remains open |
| Risk ordering and parity | C05 / I09 | R17 → R06 → R12 → R14 → R13; R06 veto; live/backtest equivalent result | fake account/filter providers, shared calculator | PARTIAL PASS — V1 in-memory calculator/adapters in `G3-EVIDENCE-LOCAL.md`; production service/runtime parity remains open |
| Candidate lifecycle | C04 / I08 | MANUAL exclusion, SEMI timeout, MariaDB terminal truth vs Redis TTL cleanup | in-memory DB/Redis state | PARTIAL PASS — lifecycle double/tests in `G3-EVIDENCE-LOCAL.md`; real persistence/reconciliation remains open |
| Confirm/timeout race | C04 | shared lock, single winner, no duplicate Step 8, idempotent cleanup | deterministic scheduler/lock double | PARTIAL PASS — deterministic single-winner test; distributed race remains open |
| Unknown order/OCO recovery | C03/C06/C07 / I06/I07/I13/I14 | UNKNOWN lookup, no blind resubmit, pending OCO recovery, readiness denial | fake order adapter and recovery state | PARTIAL PASS — in-memory recovery/readiness/snapshot tests; actual restart/runtime recovery remains open |
| Backtest isolation | C07 / I15 | no sockets, secrets, Redis, dbwriter queue, live DB writes; output only `/app/results` | network-deny guard, temp output dir | PARTIAL PASS — local forbidden-path/output guard; real profile/container isolation remains open |
| Readiness predicate | C07 / I14 | OPEN denied until infrastructure, account.synced, UNKNOWN and pending-OCO recovery complete | fake readiness/reconciliation state | PARTIAL PASS — in-memory truth-table test; deployment readiness remains open |

- Runtime restoration decision: `BLUEPRINT-G3-RUNTIME-RESTORATION.md`.
- Latest canonical evidence: `G3-EVIDENCE-LOCAL.md` — **64 passed in 0.10s**.
- Consistency audit: `G3-EVIDENCE-CONSISTENCY-AUDIT.md` classifies every row as partial local PASS or NOT_PROVEN.
- No historical test counts are active evidence; all uncovered rows remain NOT_PROVEN.

## Current workspace capability check

- Python runtime files: present under `runtime_slice/` (minimum slice only).
- Python test files: present under `tests/` (minimum slice only).
- pytest configuration: none; command uses installed `pytest` directly.
- `shared/tests/` or equivalent test directory: none found.
- Therefore uncovered G3 rows remain `IMPLEMENTATION_NOT_PRESENT`/`NOT_RUN`; only the explicitly marked partial rows have captured local evidence.

## Forbidden dependencies

G3 local-only tests must fail closed if they use or discover:

- Binance REST/WS, CCXT exchange clients, API credentials or live secrets.
- TCP Redis, MariaDB, ClickHouse, or live dbwriter service/queue.
- Docker socket, Docker Compose, macvlan, remote UDS/SSH, Portainer.
- Production signal queues, live trader, real order/OCO, or real sleeps/wall-clock assertions.

## Evidence required for G3 promotion

Each row needs a test name, source revision/hash, command, captured output, fixture boundary, and result. Blueprint/search evidence alone is insufficient. Until these artifacts exist, manifest G3 remains `PENDING` and release remains `INTEGRATION / NOT_RELEASED`.

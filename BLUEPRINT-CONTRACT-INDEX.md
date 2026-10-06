# CCURR Blueprint Contract Index

## Release status

- Blueprint release: `v4.0`
- Integrated contract release: `steps-1-7-integrated-v1`
- Current status: `INTEGRATION`
- Production code generation: **blocked until G0–G6 pass**
- Machine-readable manifest: [BLUEPRINT-MANIFEST.yaml](BLUEPRINT-MANIFEST.yaml)

This index integrates Steps 1–7. It is an index and acceptance contract, not a second definition of Python models or business schemas.

## Authority precedence

1. Manifest release policy and artifact inventory
2. Chapter 9 strategy plugin contract
3. Chapter 1 global time/numeric/data rules
4. Chapters 2–6 data, communication, container, and deployment rules
5. Chapter 7 strategy business rules
6. Chapter 8 engine orchestration
7. Chapter 10 backtest adapters
8. Chapter 11 generation guidance
9. Chapter 12 status and acceptance gates

A lower-priority summary cannot override a higher-priority contract. Any unresolved conflict is `BLOCKED`; it must not be resolved by guessing. Duplicate interface/model snippets must be labeled non-normative and link to the authority.

## Integrated contracts

| ID | Contract | Normative source | Main consumers |
|---|---|---|---|
| C01 | Strategy plugin, models, lifecycle | Chapter 9 §§9.0–9.6 | Chapters 7, 8, 10, 11 |
| C02 | UTC time, Decimal, units, DB conversion | Chapter 1 §§1.1/1.4; Chapter 9 models | Chapters 2, 7, 8, 9, 11 |
| C03 | Spot Order Intent and OCO/OTOCO | Chapter 9 §9.4.3; Chapter 6 execution rules | Chapters 7, 9, 10, 11 |
| C04 | Candidate lifecycle and Redis state | Chapter 7 §§7.7/7.7.4/7.7.6; Chapter 9 Candidate | Chapters 8, 11, 12 |
| C05 | Risk and sizing | Chapter 6 §6.6.5; Chapter 9 RiskCalculator | Chapters 7, 9, 10, 11, 12 |
| C06 | Data authority, writers, routing, events | Chapter 1 §1.6; Chapters 2–6 | All containers |
| C07 | Deployment, readiness, persistence, recovery | Chapter 6 §§6.14.3/6.15.7 | Chapters 11, 12 |

## Cross-contract invariants

- Strategy/Step time comes only from injected `Clock`/`StrategyContext`.
- Domain/API/Redis/event timestamps are UTC epoch milliseconds.
- Canonical strategy numeric fields use `Decimal`; percentage points and ratios are distinct.
- Live and backtest use the same strategy constructor/lifecycle and RiskCalculator semantics.
- All order intent is Binance Spot semantics; `reduceOnly` is forbidden.
- Retries reuse `clientOrderId`; exchange IDs are not our idempotency key.
- Pending OCO state remains until Binance accepts the OCO.
- MariaDB owns Candidate terminal truth; Redis TTL is hot-state cleanup only.
- Risk order is `R17 → R06 → R12 → R14 → R13`; R06 can veto allocation.
- Private/trading Binance APIs route through `ccurr-trader`; DB writes route through `ccurr-dbwriter`.
- Every Redis canonical key has one primary writer, with the documented position write-through/correction exception.
- Reliable events have state/DB/reconciliation recovery and cannot rely only on Pub/Sub.
- OPEN remains denied until readiness/reconciliation gates pass.
- Backtest is isolated from live sockets, macvlan, secrets, Redis, and dbwriter queues.

## Artifact roles

- Master: system entrypoint and index.
- PART01: global rules and source authority.
- PART02: database schema, Redis registry, storage mappings.
- PART03: communication routing and event reliability.
- PART04: container execution, risk, deployment and fault rules.
- Chapter 7: strategy business rules.
- Chapter 8: engine orchestration and mode handling.
- Chapter 9: sole normative plugin/model contract.
- Chapter 10: backtest implementations of canonical contracts.
- Chapter 11: generation order and prompts.
- Chapter 12: status, open issues, and release gates.
- Legacy `blueprint-v4-01.md` is not part of the current formal artifact inventory and is not used for generation. Historical references must not override the current manifest or contract files.
- `BLUEPRINT-TEMPLATE.md`: deprecated template, not a formal release artifact.

## Release gates

### G0 — Inventory completeness

All formal artifacts are listed in the manifest, every artifact has a role/status, and all references resolve.

### G1 — Authority uniqueness

Each canonical model, constructor, lifecycle, Redis contract, event contract, and container rule has one normative source. Duplicate snippets are explicitly non-normative.

### G2 — Semantic consistency

Time/numeric, Order Intent, Candidate, risk, data authority, event reliability, readiness, and backtest isolation agree across all consumers.

### G3 — Evidence

The project has contract/API, model serialization, clock, RiskCalculator parity, race, recovery, partial-fill OCO, and live/backtest parity evidence or an approved test plan.

### G4 — Operational safety

Private API routing, DB write boundary, unique Redis writers, persistence, readiness, failure matrix, and backtest isolation are consistent.

### G5 — No unresolved normative conflicts

The following are release blockers until resolved or explicitly marked historical/deprecated:

- active stop-loss buffer values disagree;
- MariaDB table count disagrees with the schema inventory;
- OTO/OTOCO/fallback terminology conflicts;
- canonical models contain float or duplicate schemas;
- direct wall-clock, DB-write, or private Binance paths remain;
- MANUAL is included in timeout queues;
- pending OCO can be deleted before success.

### G6 — Release approval

Only after G0–G5 pass may the manifest become `VERIFIED`; explicit approval is then required to set `RELEASED` and permit production generation.

## Step 9 verification record

- Schema inventory: **verified from blueprint DDL** — 3 ClickHouse tables, 20 MariaDB tables, 23 unique definitions, 24 CREATE TABLE occurrences. The Chapter 9/10 `backtest_results` DDL is now explicitly non-normative; Chapter 3 is canonical.
- Stop buffer: V1 active decision is **uniform 1.0%, no tiers**. Chapter 12 B5 is historical/superseded; tier values are future/non-active. Other `0.5` occurrences are unrelated technical percentages or historical examples and must not be interpreted as the V1 stop-loss parameter.
- Contract/search evidence: recorded as documentation evidence only; actual API, parity, race, recovery and deployment tests remain pending.
- Release decision: **NOT_RELEASED**. Manifest remains `INTEGRATION` while G3/G4 are pending and G6 approval is not started.


## Step 9 G1–G5 verification evidence

The read-only classification report is [BLUEPRINT-VERIFICATION-REPORT.md](BLUEPRINT-VERIFICATION-REPORT.md). It records evidence and remaining gates without claiming runtime verification.

Current gate summary:

```text
G0 VERIFIED
G1 VERIFIED (documentation scope)
G2 VERIFIED (documentation scope)
G3 PENDING (partial local evidence; NOT_PROVEN runtime gaps)
G4 PENDING (static/local evidence only)
G5 VERIFIED (documentation scope; legacy artifact excluded from formal inventory)
G6 NOT_STARTED
```

Search all `BLUEPRINT-*.md` and classify each occurrence as normative, reference, example, deprecated, or blocker:

strategy_cls(|StrategyContext(|time.time(|now_ms(|asyncio.sleep
float|Decimal|_pct|ratio|list[dict]|elapsed_min
OTO|OTOCO|reduceOnly|clientOrderId|pending_quantity|pending_oco|executed_qty
R17|R06|R12|R13|R14|RiskCalculator|MIN_NOTIONAL|INSUFFICIENT_BALANCE
dbwriter|ccurr-trader|Pub/Sub|UNKNOWN|reconciliation|readiness
22|16|startup|macvlan|secret|volume|backtest
```

Release status must not be raised from text search alone; required tests and unresolved issues belong in the manifest.

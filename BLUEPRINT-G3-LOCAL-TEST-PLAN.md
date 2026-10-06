# G3 Local-only Test Plan

## Purpose

本文件定義 G3 runtime/parity/race/recovery evidence 的安全執行邊界。它不是 runtime implementation，也不宣稱測試已通過。

## Runtime restoration gate

The workspace currently contains no Python runtime, tests, package metadata, or pytest runner. Do not generate implementation from snippets during a G3 evidence run. Restore or separately authorize the minimum Chapter 9/10 contract slice first; record the restoration decision in `BLUEPRINT-G3-RUNTIME-RESTORATION.md`, then execute the layers below. Until that happens, all matrix rows remain `IMPLEMENTATION_NOT_PRESENT`/`NOT_RUN` and G3 remains `PENDING`.

## Test layers

### A — Contract and model

- constructor/context builder/lifecycle parity
- Candidate status/terminal transitions
- OrderIntent Spot-only and `reduceOnly` rejection
- RiskResult and public MockBroker pending-OCO methods
- Decimal and UTC epoch-ms serialization round-trip

### B — Clock and strategy boundaries

- VirtualClock `now_ms`, `advance`, `reset`
- strategy/Step receives time only through context
- closed/open slot, elapsed and threshold boundary semantics
- no wall-clock/network dependence

### C — Order/risk parity

- clientOrderId is reused on retry
- pending OCO remains until successful placement
- partial-fill OCO uses executed quantity and fee/filter safe quantization
- exact risk order `R17 → R06 → R12 → R14 → R13`
- identical live/backtest calculator results for identical inputs

### D — Race and recovery

- Candidate confirm-vs-timeout has one winner
- duplicate callback cannot execute Step 8 twice
- UNKNOWN order is queried before any retry
- pending OCO survives failed placement and restart recovery
- readiness remains DENY until required recovery state is complete

### E — Isolation and forbidden paths

- block network/socket access
- block real Redis/DB/Docker/SSH/Binance clients
- verify no secrets are read
- verify backtest writes only isolated `/app/results` equivalent
- verify no production queue or real-trading side effect

## Required evidence artifact

For each test batch record:

- test source path and source hash;
- exact local command;
- Python/pytest versions;
- fixture and dependency boundary;
- stdout/stderr and exit code;
- pass/fail count;
- isolation guard result;
- known limitations.

Use status values `PLANNED`, `IMPLEMENTATION_NOT_PRESENT`, `NOT_RUN`, `PASS`, or `FAIL`. Do not use `PASS` for a document-only inspection.

## Safety stop conditions

Stop before executing if any test attempts to:

- resolve a real exchange client or Binance credential;
- open a non-loopback network connection;
- connect to Redis/MariaDB/ClickHouse or dbwriter;
- use Docker, remote UDS, SSH, macvlan or Portainer;
- modify production configuration, queues, databases or files outside the isolated result directory.

## Promotion rule

G3 remains `PENDING` until the required local-only tests have executable subjects and captured evidence for model/clock/risk/order/parity/race/recovery/isolation areas. G4 remains independent and pending until operational verification is separately authorized and evidenced.

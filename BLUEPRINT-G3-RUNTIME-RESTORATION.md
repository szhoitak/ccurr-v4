# G3 Runtime Restoration Decision Record — 2026-10-05

## Decision

Do not fabricate or infer a Python runtime from Blueprint snippets. The current `ccurr-v4` workspace is Blueprint-only: no Python source, tests, package configuration, or pytest runner exists. G3 runtime evidence cannot be executed until an implementation source is restored or a separately approved implementation task creates it.

## Canonical minimum slice when implementation is authorized

The first reviewable implementation slice must be derived from the existing canonical Chapter 9/10 contracts, not from historical V3 code:

- `Clock` and `VirtualClock` (`now_ms`, `advance`, `reset`, `is_finished`)
- Decimal/UTC epoch-ms model validation and serialization
- `Candidate`, `Signal`, `OrderIntent`, `OrderIdentity`, `RiskResult`
- `StrategyContext` / `BacktestContext` boundary with fake providers
- `MockBroker` public pending-OCO methods
- a `RiskCalculator` protocol boundary; no invented sizing formula beyond the Blueprint
- deterministic in-memory fixtures and local-only tests

This slice is test infrastructure and contract implementation only. It must not include Binance, CCXT, Redis, MariaDB, ClickHouse, Docker, UDS, production queues, secrets, or live deployment wiring.

## Required review before implementation

Before creating source files, compare each proposed class/method/field to:

- Chapter 9 §§9.3–9.4.5 and Chapter 10 §§10.2, 10.4–10.6;
- Chapter 11 G3/local testing requirements;
- Chapter 12 acceptance and isolation rules;
- `BLUEPRINT-G3-EVIDENCE-MATRIX.md` and `BLUEPRINT-G3-LOCAL-TEST-PLAN.md`.

Potential Blueprint decisions that must not be silently invented include full RiskCalculator formula details, Candidate terminal handling for `CANCELED`, provider method return schemas, and live adapter behavior.

## Current evidence state

- Runtime restoration: `IMPLEMENTATION_NOT_PRESENT`
- Test execution: `NOT_RUN`
- G3: `PENDING`
- G4: `PENDING`
- Release: `INTEGRATION / NOT_RELEASED`

## Safety boundary

No historical source directory was found at the old path, and no external repository, GitHub remote, Docker host, or deployment target may be queried as part of this restoration without separate authorization. Any restored source must be inspected, hashed, and tested with the local-only guards before it can provide G3 evidence.

# G3 Local Evidence — Minimal Runtime Slice

**Date:** 2026-10-05  
**Scope:** deterministic local-only runtime evidence; not full G3 completion. Canonical latest run: **69 passed**.

## Exact commands and results

```text
py -m pytest tests -q
74 passed in 0.14s

py -m compileall -q runtime_slice tests
```

Environment: Python 3.14.6, pytest 9.1.1.

## Covered partial evidence

- Clock, UTC epoch-ms, Decimal and typed model boundaries.
- Spot OrderIntent/reduceOnly rejection and retry clientOrderId identity.
- Candidate MANUAL/SEMI lifecycle, TTL non-terminal semantics, deterministic confirm/timeout winner.
- UNKNOWN query-before-retry, pending OCO retention/recovery, readiness truth table, snapshot/restore doubles.
- Step 2 typed offline fixture/provider/parity and requested boundary cases.
- V1 Decimal risk boundary R17→R06→R12→R14→R13, fee modes, rejection metadata, live/backtest boundary adapter parity.
- Strategy constructor/lifecycle/context-builder parity boundary.
- Order/OCO safety: executed_qty reserve, quantization, minQty/minNotional, failure retention, retry identity.
- Backtest offline provider, registry, metrics, sweep failure isolation, MockBroker trade/equity flow, OCO TP/SL close-out and explicit dual-trigger ambiguity.
- Static/local isolation guards and isolated result output.
- Phase 1 shared-kernel models: AccountSnapshot, SymbolFilters, BacktestSettings, OrderResponse, Position, Trade, EquityPoint; Decimal/UTC-ms round-trip; UNKNOWN/retry fields.
- Phase 1 error taxonomy and provider/adapter Protocols: transport-neutral stable codes and local fake type-shape checks.
- Phase 1 kernel coverage: wire aliases, UNKNOWN OrderResponse/retry correlation, BacktestSettings isolation, Protocol fake shape, and stable error-code taxonomy.

## Isolation boundary

No Binance/CCXT, Redis, MariaDB, ClickHouse, dbwriter, Docker, SSH, UDS, macvlan, production queue, secrets, network calls, real sleeps, or real trading were used. The suite is deterministic and in-memory.

## NOT_PROVEN / remaining gaps

- Full plugin loader/production StrategyEngine and service integration.
- DB/Redis adapter round-trip and MariaDB terminal reconciliation.
- Real exchange transport, response/error parity and real partial-fill behavior.
- Distributed lock/race semantics and real restart recovery.
- Real Compose/profile/network/secret/volume/readiness verification.
- Complete live/backtest production service parity.
- Real OCO trigger priority when TP and SL occur in one bar.
- Calibrated Sharpe/production reporting and complete BacktestEngine metrics pipeline.

## Status

This is partial local evidence only. G3 remains `PENDING`; G4 remains `PENDING`; release remains `INTEGRATION / NOT_RELEASED`.

Source hashes must be regenerated with `sha256sum runtime_slice/*.py tests/*.py` after any further file change.

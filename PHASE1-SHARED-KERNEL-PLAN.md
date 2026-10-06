# Phase 1 Shared Kernel Plan — Local-only

## Status

Phase 0 model freeze is complete. This document plans Phase 1 shared-kernel implementation only. It does not authorize production generation, Docker, remote services, Binance, database connections, or release.

## Contract mapping

| Phase 0 contract | Current runtime_slice source | Phase 1 action |
|---|---|---|
| AccountSnapshot/SymbolFilters | `risk_v1.py` local dataclasses | move to shared kernel module; add captured_at/source/symbol/tick_size fields |
| OrderResponse | absent | add canonical transport-neutral model with UNKNOWN/retry semantics |
| Position/Trade/EquityPoint | partial local broker records | unify shared models and aliases; keep Decimal/UTC-ms validation |
| BacktestSettings | absent | add offline-only settings model and secret/live dependency rejection |
| ContextBuilder | `context.py` Protocol | retain as sole protocol; add parity/return-shape tests |
| Decimal/UTC-ms | `values.py` | promote serializer/validator API and round-trip tests |
| Error taxonomy | absent | add stable domain errors without exchange-specific adapter implementation |

## Work packages

### 1. Shared models and wire aliases

Implement one canonical model module for AccountSnapshot, SymbolFilters, BacktestSettings, OrderResponse, Position, Trade, EquityPoint and existing Strategy models. Use explicit aliases only where the wire contract requires them; no duplicate service-local schemas.

Acceptance:

- required/optional fields match Phase 0;
- Decimal fields reject binary float;
- `_ms` values validate UTC epoch-ms;
- UNKNOWN OrderResponse preserves clientOrderId and cannot be treated as ordinary rejection;
- round-trip serialization retains Decimal strings and aliases.

### 2. Serializers

Extend Decimal/UTC helpers with deterministic `to_wire`/`from_wire` boundary. Do not implement Redis/DB adapters yet. Reject NaN, infinity, float and invalid timestamp values. Preserve stable sorted JSON for evidence hashes.

### 3. Error taxonomy

Add local domain errors:

- `ContractValidationError`
- `TimestampValidationError`
- `DecimalValidationError`
- `OrderIdentityError`
- `UnknownOrderStateError`
- `ReadinessDeniedError`
- `IsolationViolationError`

Errors must be transport-neutral and contain no secrets or raw exchange responses.

### 4. Provider and adapter protocols

Define Protocols only, with no network implementations:

- `KlineProvider`
- `ConfigProvider`
- `PositionProvider`
- `AccountProvider`
- `FilterProvider`
- `OrderTransport`
- `ResultWriter`
- `RecoveryStore`

All live/backtest differences remain injected adapters. Protocol methods use canonical shared models.

### 5. Tests

Add local-only tests for:

- every Phase 0 model round-trip;
- wire aliases and Decimal/UTC-ms validation;
- ContextBuilder parity;
- OrderResponse UNKNOWN/retry correlation;
- BacktestSettings isolation rejection;
- protocol fakes/type-shaped behavior;
- error code stability.

## Gate and evidence

Phase 1 tests may increase partial local evidence but cannot promote G3. Production service integration, adapter round-trip, real exchange parity, distributed recovery, and G4 remain NOT_PROVEN. Update `G3-EVIDENCE-LOCAL.md` and the matrix only with actual test results. Keep release `INTEGRATION / NOT_RELEASED`.

## Non-concurrent boundaries

- Do not add Redis/MariaDB/ClickHouse/Binance implementations in Phase 1.
- Do not generate service-specific duplicate models.
- Do not mark external adapters verified from Protocol tests.
- Do not enable live keys, AUTO, deployment, or production generation.

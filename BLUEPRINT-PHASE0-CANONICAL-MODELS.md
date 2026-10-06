# Phase 0 Contract Freeze — Canonical Models and OCO Policy

**Date:** 2026-10-05  
**Status:** INTEGRATION / NOT_RELEASED. This document freezes contracts for planning only; it does not authorize production generation, deployment, or release.

## Authority and resolution rules

1. Chapter 9 is the sole normative source for strategy-facing models, ContextBuilder, and lifecycle.
2. Chapter 10 supplies offline implementations of canonical contracts only.
3. Chapter 11 generation guidance and Chapter 12 status/gates cannot create a second schema.
4. Where this file resolves a previously missing model, the resolution is additive to Chapter 9/10 and must be reflected in generated shared models before service implementation.
5. Undefined exchange/deployment behavior remains `NOT_PROVEN`, not an implicit default.

## Canonical shared models

### AccountSnapshot

Owned by the risk boundary; authoritative values originate from accountsync/Binance in live mode and MockBroker/in-memory provider in backtest.

Required fields:

- `total_account_value: Decimal`
- `free_usdt: Decimal`
- `strategy_allocation_pct: Decimal` (percentage points)
- optional `captured_at_ms: int` (UTC epoch-ms)
- optional `source: str` (`LIVE_ACCOUNT_SYNC` / `BACKTEST_MEMORY`)

All monetary values are Decimal. No model may contain API credentials or raw exchange client objects.

### SymbolFilters

Owned by the exchange/filter provider; consumed read-only by RiskCalculator and order safety.

Required fields:

- `min_qty: Decimal`
- `step_size: Decimal`
- `min_notional: Decimal`
- `tick_size: Decimal` (required for price quantization)
- `symbol: str`
- optional `captured_at_ms: int`

R12 quantizes quantity down by `step_size`; price adapters use `tick_size`. R14 rejects below `min_qty`/`min_notional`; it never increases a rejected quantity.

### ContextBuilder

Canonical protocol:

```text
build(strategy_id: str) -> StrategyContext
```

The strategy constructor is always `(config, context_builder)`. Live and backtest builders expose the same strategy-facing Context API; only injected Clock/provider/adapter implementations differ. A builder must not open external connections during construction in the contract test boundary.

### BacktestSettings

Offline-only configuration boundary:

- `start_ts: int` UTC epoch-ms
- `end_ts: int` UTC epoch-ms
- `symbols: list[str]`
- `timeframes: list[str]` default `1d/4h/1h`
- `step_ms: int` default `300000`
- `initial_balance: Decimal`
- `output_dir: str`
- `force_auto: bool = True`

BacktestSettings must not contain live secrets, Redis/dbwriter endpoints, live socket paths, or exchange clients. Any future HTTP/UDS API is an adapter contract and is not required for the minimum slice.

### OrderResponse

Transport-neutral trader boundary response:

- `ok: bool`
- `status: str` (`NEW`, `FILLED`, `CANCELED`, `REJECTED`, `UNKNOWN`)
- `client_order_id: str`
- optional `exchange_order_id: str`
- optional `order_list_id: str`
- `executed_qty: Decimal`
- optional `avg_price: Decimal`
- optional `error_code: str`
- optional `error_message: str`
- `received_at_ms: int` UTC epoch-ms

`client_order_id` is the internal idempotency key. `UNKNOWN` is not a rejection and must enter query/reconciliation flow; retry must reuse the same client ID.

### Position

In-memory/backtest and order-state model:

- `symbol: str`
- `quantity: Decimal`
- `entry_price: Decimal`
- optional `realized_pnl: Decimal`
- optional `updated_at_ms: int`

MariaDB/order state and Binance/accountsync remain authoritative in live mode; this model is not a replacement for those stores.

### Trade

A completed fill/close record:

- `symbol: str`
- `side: BUY | SELL`
- `quantity: Decimal`
- `price: Decimal`
- `fee: Decimal`
- `pnl: Decimal | None`
- `timestamp_ms: int`
- `client_order_id: str`
- optional `entry_order_id: str`
- optional `exit_type: TAKE_PROFIT | STOP_LOSS | MANUAL | RECOVERED_CLOSE`

The exact exchange fee asset conversion remains adapter responsibility; no float conversion is allowed.

### EquityPoint

- `timestamp_ms: int`
- `equity: Decimal`
- optional `cash: Decimal`
- optional `unrealized_pnl: Decimal`

Equity curves are ordered by UTC timestamp and are offline result data; they are not live DB truth.

## OCO same-bar priority policy

**Decision for V1:** if a single bar satisfies both TP and SL, the engine returns `AMBIGUOUS_DUAL_TRIGGER`, does not silently choose a leg, does not consume pending OCO state, and records a critical/manual-review condition. This conservative policy avoids inventing intrabar ordering from OHLC data.

A future version may use lower-timeframe/tick data to resolve ordering, but that is outside V1 and remains `NOT_PROVEN` until separately specified and tested.

## Acceptance checklist

- [ ] Shared models are implemented once and imported by live/backtest adapters.
- [ ] Decimal and UTC epoch-ms validators/serializers pass round-trip tests.
- [ ] ContextBuilder parity test passes for live/backtest-shaped builders.
- [ ] BacktestSettings rejects live dependencies/secrets and writes only isolated results.
- [ ] OrderResponse UNKNOWN/retry correlation tests pass.
- [ ] Position/Trade/EquityPoint deterministic MockBroker tests pass.
- [ ] Same-bar dual-trigger test expects `AMBIGUOUS_DUAL_TRIGGER` and pending state retention.
- [ ] No production generation or deployment occurs before G3/G4/G6 gates.

## Current release boundary

This contract freeze enables Phase 1 shared-kernel planning only. It does not promote G3/G4, does not mark any external adapter verified, and does not change `INTEGRATION / NOT_RELEASED`.

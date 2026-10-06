# Production Runtime Implementation Plan — v4

## Status and boundary

This is a staged implementation plan, not a release approval and not a claim that production runtime exists. The current `runtime_slice/` is a local contract/evidence harness. Production generation remains blocked while G3/G4/G6 are incomplete.

## Phase 0 — Contract freeze and evidence baseline

**Status:** Phase 0 contract freeze artifact created as `BLUEPRINT-PHASE0-CANONICAL-MODELS.md`.

**Inputs:** Chapter 9 canonical plugin/models/lifecycle; Chapter 1 Decimal/time; Chapters 3–6 routing/storage/recovery; Chapter 11 generation order; Chapter 12 gates.

**Deliverables:** `BLUEPRINT-PHASE0-CANONICAL-MODELS.md`; versioned model/event/key/API matrices; `NOT_PROVEN-ACCEPTANCE-MATRIX.md`; source/evidence hashes; explicit decisions for same-bar OCO priority, missing referenced models, backtest result exporter, and readiness predicate.

**Gate:** no production code generation; all unresolved semantics recorded as BLOCKED/NOT_PROVEN.

## Phase 1 — Production shared kernel

**Planning artifact:** `PHASE1-SHARED-KERNEL-PLAN.md`. Implementation remains local-only and is not production release.

Promote only reviewed parts of `runtime_slice` into a package boundary:


- Decimal/UTC-ms validators and serializers;
- canonical models and wire aliases;
- injected Clock and ContextBuilder/provider protocols;
- OrderIntent/OrderIdentity and error taxonomy;
- trace/audit interfaces without live transport.

**Tests:** model round-trip, no float/wall-clock, constructor/lifecycle contract.  
**Gate:** package contract passes; no service integrations yet.

## Phase 2 — Strategy core

Implement BaseStrategy/BaseStep, plugin registry/loader, StrategyEngine task lifecycle, config validation and typed Step 1–8 outputs. Keep all external providers behind protocols.

**Tests:** loader duplicate/unknown behavior, Step 2 boundaries, deterministic replay, lifecycle timeout, strategy logs.  
**Gate:** offline strategy run only; no live order path.

## Phase 3 — Offline backtest consumer

Build HistoricalDataProvider, BacktestContext through the canonical ContextBuilder, MockBroker order/fill/OCO adapters, VirtualTimeoutQueue, PerformanceAnalyzer, JSON/HTML writer and isolated ParameterSweep.

**Tests:** deterministic replay, metrics reference fixtures, sweep failure isolation, same-bar OCO decision, no Redis/secrets/live sockets/dbwriter.  
**Gate:** offline backtest is reproducible and isolated; this does not authorize live trading.

## Phase 4 — Durable data plane

Implement schema migrations and adapters for MariaDB/ClickHouse plus Redis key registry, dbwriter queues/backpressure/retry/fallback and reconciliation contracts. Enforce one primary writer per canonical key.

**Tests:** adapter round-trip, migration/query, duplicate-writer checks, TTL-not-terminal, fallback/replay, crash-window fixtures.  
**Gate:** persistence evidence and recovery fixtures pass before service integration.

## Phase 5 — Trader and ingestion boundaries

Implement ccurr-trader private API boundary, accountsync, websocket and k* data ingestion. Keep secrets only in trader; use fake transport and sandbox only after local contracts pass.

**Tests:** correlated responses, rate limits, exchange filters, clientOrderId idempotency, UNKNOWN query-before-retry, routing/static checks, degraded data handling.  
**Gate:** no AUTO/live keys; sandbox authorization required for external verification.

## Phase 6 — Paper-first execution state machine

Implement risk adapter, executor/order/override state machines, pending OCO retention, partial-fill safe quantity, UNKNOWN/recovery loops and readiness controller. Keep paper/mock mode fail-closed.

**Tests:** R17→R06→R12→R14→R13 parity, adversarial race, restart/reconciliation doubles, readiness fault matrix, emergency close.  
**Gate:** paper-only end-to-end; OPEN denied until all recovery gates pass.

## Phase 7 — Candidate lifecycle and interface services

Implement MariaDB-authoritative Candidate lifecycle, Redis hot state, MANUAL/SEMI/AUTO routing, confirm/timeout locks/atomic cleanup, Telegram-independent command boundary and notifications/buffer.

**Tests:** exactly-once Step 8, MANUAL exclusion, TTL cleanup, notification failure isolation, restart recovery.  
**Gate:** lifecycle can run with fake executor; do not combine with AUTO rollout.

## Phase 8 — Operations and deployment verification

Implement monitor/degradation/readiness, heartbeats/audit/trace, persistence backup/restore, Compose profiles and healthchecks. Validate 22-container startup layers and backtest physical isolation.

**Tests:** static Compose validation, healthcheck/readiness truth table, volume restore, fault injection, secret/network isolation.  
**Gate:** G4 operational evidence; external deployment requires a separate explicit authorization.

## Phase 9 — Staged integration and release

Run full local contract/E2E suite, then authorized sandbox/paper verification, followed by staged MANUAL/SEMI observation. Only after G0–G5 evidence is complete may a human approve G6 and change the manifest to `RELEASED`.

## Non-concurrent work

- Do not enable live keys/AUTO during Phase 5–8 validation.
- Do not integrate services before model/schema/key contracts are frozen.
- Do not share live Redis/dbwriter/Compose state with backtest.
- Do not implement OCO cleanup simultaneously with unverified retry/recovery semantics.
- Do not treat local doubles as production evidence.

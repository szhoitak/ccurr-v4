# G3 Evidence Consistency Audit — 2026-10-05

## Canonical executed result

```text
Command: py -m pytest tests -q
Result: 64 passed in 0.10s
Compile: py -m compileall -q runtime_slice tests — passed
Python: 3.14.6
pytest: 9.1.1
```

The previous evidence file contained stale counts (10/19/26/33/35/41/47/51/55/58/61) and repeated coverage bullets. The current canonical count is **64 tests**. Historical counts are removed from the active evidence narrative.

## Matrix classification

| Evidence class | Matrix rows | Current status | Meaning |
|---|---|---|---|
| Partial local PASS | model/API; Decimal/epoch-ms; Clock; Step 2 offline/provider; order identity; pending OCO/partial-fill safety; Risk V1 boundary; Candidate lifecycle; deterministic confirm/timeout; UNKNOWN/OCO in-memory recovery; backtest forbidden-path/output guard; readiness truth table; strategy lifecycle; registry/backtest boundary; metrics/sweep; MockBroker execution; OCO trigger/close-out | `PARTIAL PASS` | Deterministic in-memory or static/local evidence exists; not production/runtime proof. |
| NOT_PROVEN | full plugin loader/engine; DB/Redis adapter round-trip; exchange transport; production RiskCalculator service; distributed locks/races; MariaDB/Redis reconciliation; real restart recovery; real Compose/profile isolation; real backtest runtime profile; real OCO trigger priority; live/backtest service parity; calibrated Sharpe/production reporting | `NOT_PROVEN` | No evidence in this workspace; must not be called PASS. |

## Evidence boundary

All tests run with in-memory/deterministic fixtures. No Binance, CCXT, Redis, MariaDB, ClickHouse, Docker, SSH, UDS, macvlan, production queue, secrets, or real trading was used. Static/local PASS does not promote G3 or G4.

## Gate conclusion

- G3: `PENDING` — broad partial local evidence exists, but required production/runtime parity, race, recovery and isolation areas remain NOT_PROVEN.
- G4: `PENDING` — static/local operational evidence exists; no deployment/runtime/persistence/restart verification.
- Release: `INTEGRATION / NOT_RELEASED`.

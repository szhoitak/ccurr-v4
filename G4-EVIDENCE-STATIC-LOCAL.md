# G4 Static/Local Evidence — 2026-10-05

## Scope

本 evidence 僅涵蓋不連 Docker、遠端主機、Redis、MariaDB、ClickHouse 或 Binance 的 Blueprint/static/local checks。它不是部署驗收，也不把文件文字當成 runtime proof。

## Commands

```text
py -m pytest tests -q
10 passed in 0.02s
py -m compileall -q runtime_slice tests
```

The local runtime slice uses only in-memory objects and an autouse network guard. No external service was contacted.

## Static checks performed

| Check | Result | Evidence |
|---|---|---|
| Private/trading Binance routing is trader-only; public kline/WS/exchangeInfo exceptions explicit | PASS (documentation scope) | PART03 §5.2; PART01 §1.6 |
| DB writes route through dbwriter; backtest result writes only `/app/results` | PASS (documentation scope) | PART01 §1.6; PART03 §5.2; PART04 §6.14.2/6.15.7 |
| `price:latest` sole writer is websocket | PASS (documentation scope) | PART01 §1.6; PART02 §4.2; PART04 §6.14.4 |
| pending order/OCO ownership is executor-create/order-update/recovery | PASS (documentation scope) | PART02 §4.3/owner contract; PART04 §6.14.4 |
| trace keys are append-only telemetry exception | PASS (documentation scope) | PART01 §1.6/§2.1; PART04 §6.14.4 |
| OPEN readiness includes infrastructure, account sync, UNKNOWN and pending-OCO recovery | PASS (documentation scope) | PART04 §6.15.7; Chapter 11/12 readiness rules |
| backtest has no live sockets/macvlan/secrets/Redis/dbwriter path | PASS (documentation scope) | PART04 §6.15.7; PART03 §5.2; Chapter 9 §10.14 |
| G3 local-only executable guard | PASS (minimum slice only) | `tests/conftest.py`; `G3-EVIDENCE-LOCAL.md` |

## Safety and isolation

- No Docker or Docker socket.
- No SSH/remote host/UDS/macvlan.
- No Redis/MariaDB/ClickHouse connections.
- No Binance/CCXT imports, API calls or credentials.
- No production queue or database mutation.
- No live deployment or restart.

## Limitations

- Static PASS is documentation-scope evidence, not runtime operational verification.
- No Compose/profile/healthcheck execution was performed.
- No volume restore, restart, UDS permission, network policy, or persistence recovery was executed.
- G4 therefore remains `PENDING`; a sandbox/L1 operational run would require separate explicit authorization.

## Conclusion

The Blueprint routing, ownership, readiness and backtest isolation claims are internally aligned at static/local scope, and the local-only runtime guard passed with the 10-test minimum slice. This does not promote G4 to VERIFIED and does not authorize deployment.

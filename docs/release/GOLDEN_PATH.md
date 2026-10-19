# Golden path (C1 release gate)

**Criterion:** sign in, add a holding, priced P&L, open the stock report, create a price alert, alert fires, APNs delivered, tap opens that stock.

A build ships only when this whole path works for a brand-new user. It is one path on purpose: the gate stays short enough to run every time.

## Automated backend half

`backend/tests/test_golden_path.py` (one test, `test_golden_path`) walks the path against the main app with the conftest client and the temp SQLite test DB:

1. Register a fresh user, then log in (`login.json`).
2. `POST /portfolio/add`: 10 TCS at 3500.
3. `GET /portfolio/{uid}` with the quote faked at 3600: `pnl_inr` is 1000.0 (`portfolio.json`).
4. `GET /api/v1/research/stocks/TCS` on a seeded report, engine mode on; ml-engine compute and the LLM fail the test if called.
5. `POST /alerts/add` for "above 3550" (`add_alert.json`), then `GET /alerts/{uid}` with one alert (`alerts.json`).
6. `POST /api/v1/notifications/register` with a device token.
7. One price-alert poller pass (`alerts_service._poll_once`) with APNs replaced by a recorder.
8. Exactly one push for the user with `ticker` TCS (and `notification_id` once habit-notif-service is merged); the newest inbox item has `action_url` `nivesh://analyze/TCS` (`inbox.json`).

Prices, ml-engine, the LLM and APNs are fakes, and the TEST-13 socket guard stays on, so the test never touches the network. It runs in backend CI with the rest of `backend/tests` (TEST-06).

Each response is compared with its recording in `docs/contract/golden/`. The key sets must match in both directions at every depth, and every recorded non-null value must keep its JSON type (int and float both count as number). A recorded `null` only requires the key to exist. A renamed, dropped or added field therefore fails this test, and the iOS contract test decodes the same files, so neither side can drift silently.

`docs/contract/golden/requests.json` holds the request bodies (register, login, add_holding, add_alert, device_register). It is hand-written and is not re-recorded.

## Recording fixtures

The five response files (`login`, `portfolio`, `alerts`, `add_alert`, `inbox`) are recordings of the hermetic run. Record them on a dev machine:

```
cd backend && GOLDEN_RECORD=1 ../venv/bin/python -m pytest tests/test_golden_path.py -q
```

Use your backend virtualenv's interpreter if it lives elsewhere (for example `venv/bin/python` inside `backend/`).

What is normalised before writing and before comparing:

- `access_token`, `refresh_token` and `token` strings become `<token>`;
- `username` becomes `golden_user`;
- `user_id` integers become 7;
- `id` and other `*_id` integers become 1;
- `*_at`, `timestamp` and `as_of` strings become `2026-01-01T00:00:00Z`.

Files are written with sorted keys and two-space indentation, so diffs stay small.

- Review the diff before committing. Every changed key must be a change you intended.
- Commit `docs/contract/golden/*.json`, then run the test again without `GOLDEN_RECORD` and confirm it passes.
- Re-record whenever an intended API change lands on any of these five responses, and in the same change update the iOS models that decode them.

The files first committed are best-effort seeds written from the serializers, because the backend cannot run where they were written. The owner replaces them with a real recording before trust-golden-ios lands.

## Automated iOS half

- `stockmeTests/GoldenPathContractTests.swift` drives the real `NetworkManager` methods through `StubURLProtocol` over the same golden files. It checks the request bodies the app sends against `requests.json`, and that every field the path displays decodes non-nil and equals the fixture. It runs in iOS CI (TEST-17).
- `stockmeUITests/GoldenPathUITests.swift` is run by the team on a Debug build against `scripts/golden_path_stub_server.py` on 127.0.0.1:8765. It needs FIX:AUTH-20 (http to loopback in DEBUG). Before typing anything it waits for the app's first request to show in the stub's `/__hits`, and after registration it requires `POST /register` or `POST /login` there. If either guard fails, the app is not talking to the stub: fix that first.
- Real APNs delivery is never automated. It is covered by the manual checklist below.

## Manual checklist for every TestFlight build

Run on a real device with a signed TestFlight build and production APNs.

1. Fresh install: delete the app, then install the TestFlight build.
2. Register a new account (accept the policy, confirm 18+).
3. Add TCS as a holding (shares and buy price of your choice).
4. See P&L: the holding shows a live price and a P&L in rupees, not "unavailable".
5. Open the report: tap TCS and the stock report loads.
6. Create an alert just above the current price ("above", a few rupees over the last price).
7. Receive the push within the poller interval (5 minutes) once the price crosses. If the market is closed, use a target the last price already meets.
8. Tap the push and land on the TCS report.

Spot checks:

- **Push permission denied:** deny notifications at the prompt, trigger an alert. No push arrives, the app does not crash, and the alert appears in the in-app inbox.
- **Offline:** turn on Airplane Mode and open Portfolio and the report. The app shows its offline or error state, never fake numbers, and recovers when the network returns.

## Exit criteria

- Backend half: `test_golden_path.py` green in CI against real recordings (end of Step 1).
- iOS half: `GoldenPathContractTests` green in CI; `GoldenPathUITests` green on a Debug build against the stub.
- Manual: all 8 steps and both spot checks pass on the TestFlight build being released (end of Step 2).
- Any failure blocks the release until it is fixed or the criterion is formally changed here.

## Sign-off

Record one line per TestFlight build before submitting it for review.

| Date | Build (CFBundleVersion) | Backend CI | iOS CI | UI test (stub) | Manual 1-8 | Spot checks | Signed off by |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

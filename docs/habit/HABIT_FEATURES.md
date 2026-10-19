# Habit features runbook

How the habit cluster (notifications, Today, Event Radar, widget, watchlist) behaves and how to
operate it. Features: I37 notification plumbing, I38 Today, I31 Event Radar, I39 widget,
I32 watchlist. Source of truth for the contracts: the habit cluster spec. Everything here is
factual information about the app; nothing in this cluster gives investment advice.

## 1. Flags

Flags live in `backend/services/feature_flags.py`. Each one is read from the env var
`FEATURE_<NAME>` on every call. `on` accepts `1/true/yes/on`, `off` accepts `0/false/no/off`;
any other value falls back to the default and logs one warning. `shadow` is accepted only by
`event_radar`. The public `GET /api/v1/features` returns
`{"flags": {name: bool}, "ttl_seconds": 300}`; `shadow` reads as `false` there. iOS caches the
response and falls back to the defaults when it is missing.

| Flag | Env var | Values | Default | Gates | Preconditions |
|---|---|---|---|---|---|
| `notif_prefs_v2` | `FEATURE_NOTIF_PREFS_V2` | off/on | off | `GET/PUT /api/v1/notifications/preferences`; category, quiet-hours and cap rules in `notify()`; results reminders (job `habit_earnings_reminders`, category `earnings_reminder`); iOS Notifications, Quiet hours and Push diagnostics rows | APNs key installed on the server and a real push verified in Push diagnostics |
| `today_brief` | `FEATURE_TODAY_BRIEF` | off/on | off | `GET /api/v1/today`; the weekday brief push (job `habit_brief_push`, category `daily_brief`); the iOS Today card and screen | Engine at Stage 3 (`RESEARCH_ENGINE_MODE=on`) and the NSE data licence confirmed |
| `event_radar` | `FEATURE_EVENT_RADAR` | off/shadow/on | off | `shadow`: NSE RSS fetch and ingest into `stock_events`, no pushes, no user display. `on`: fetch, ingest, pushes (category `events`), `GET /api/v1/events` and the iOS "Filings and events" section | Legal sign-off on fetching, storing and displaying NSE RSS filings, before any value other than off |
| `watchlist_v2` | `FEATURE_WATCHLIST_V2` | off/on | off | iOS since-added chip and sort menu on the watchlist | Owner decision |
| `widget_snapshot` | `FEATURE_WIDGET_SNAPSHOT` | off/on | on | Kill switch: off clears the App Group widget snapshot, blanking every widget | Leave on |

Notes per flag:

- `notif_prefs_v2` also gates results reminders. They read only users' own saved results
  dates (`earnings_alerts`) and never touch NSE, so they do not wait for `event_radar`.
  With the flag off, `notify()` applies only the master switch (`alerts_enabled`), exactly as
  the fix-track pipeline did.
- `today_brief` is one global flag, and `/api/v1/features` is public, so turning it on shows
  Today to every user. Test it on a staging server with `RESEARCH_ENGINE_MODE=on`. Never turn
  it on early in production to test it.
- `event_radar` in `shadow` already polls NSE about 600 times a day and stores filing
  subjects. In shadow, `GET /api/v1/events` answers admin accounts only, for the review.
- `portfolio.added_price` capture is not flagged: it always runs, because history that is not
  captured cannot be recovered. Only the visible watchlist UI sits behind `watchlist_v2`.

**Rollback.** Set the flag to `off` in `backend/.env` and restart the backend. Flags are read
from the env and `main.py` loads `.env` at boot, so nothing changes until the restart. Turning a
flag off leaves stored rows in place (preferences, inbox rows, `stock_events`); iOS hides the
gated surfaces at its next flags refresh (TTL 300 s) and the gated endpoints answer 404
`FEATURE_DISABLED`.

## 2. Enable sequence

Ship the iOS build that carries the flags client first; older builds ignore the new endpoints.
Each step is a change to `FEATURE_*` in `backend/.env` followed by a restart.

1. Verify push in Settings > Push diagnostics on a TestFlight build: the test push outcome is
   `sent` ("Sent to this device") and the APNs topic matches the bundle id
   (`saumypatel.stockme`).
2. Turn on `notif_prefs_v2` (`FEATURE_NOTIF_PREFS_V2=on`). Results reminders start with it.
3. Get legal sign-off on fetching, storing and displaying NSE RSS filings.
4. Set `event_radar=shadow` (`FEATURE_EVENT_RADAR=shadow`) for 14 days.
   Do not set FEATURE_EVENT_RADAR to shadow before legal sign-off; shadow fetches from NSE.
5. Review 50 stored `stock_events` with the query in section 5. Type and symbol must be correct
   in at least 95% of them (at most 2 wrong out of 50). Below that, stay in shadow and fix the
   classifier or mapping first.
6. Set `event_radar=on` (`FEATURE_EVENT_RADAR=on`).
7. Turn on `today_brief` (`FEATURE_TODAY_BRIEF=on`) only when the engine is at Stage 3
   (`RESEARCH_ENGINE_MODE=on`) and the data licence is confirmed.
8. Turn on `watchlist_v2` (`FEATURE_WATCHLIST_V2=on`) when the owner decides.

`FEATURE_WIDGET_SNAPSHOT` stays `on` throughout.

## 3. Engine conflict decisions

Where the roadmap conflicted with the Research Engine, the engine decision won:

- **No LLM brief, and English only** (engine D19/D20: no LLM on request paths, English-only v1).
  Today, the brief push and Event Radar copy are fixed server templates and rules. A backend
  test runs lexicon `lx-1` over every template.
- **`/daily-action` returns 410 from Stage 3** (D24). Today replaces it; while `today_brief` is
  on, iOS skips the daily-action and morning-summary requests.
- **Prices are shown only when the engine mode is on.** Today reads only engine snapshot facts
  (no yfinance calls), so it inherits the Stage-3 data-licence gate. With any other mode,
  freshness is `unavailable` and Today shows only alerts, saved results dates and filings.
- **Condition for a future `today_brief_llm`** (default off, not built): all of
  - engine v1.1 `portfolio_facts`;
  - reuse of validator `gv-1`;
  - FINSEC-04 `ai_processing` consent;
  - a reviewed Hindi lexicon (engine open question 6).

## 4. Deferral conditions

**Event Radar full version** waits for:

- one events table absorbing `market_anomalies`, `signal_events`, `risk_signals` and
  `macro_events`, plus `alert_rules` absorbing `price_targets` and `earnings_alerts`; this needs
  the data cluster's C15 ingestion worker and I14 instrument master;
- per-stock 'notify me about' toggles, once I47 measures opt-out;
- ASM/GSM inclusion after a data-rights review (REG-10);
- BSE filings with cross-exchange dedupe.

**Pledge (promoter encumbrance) events** are stored, but not pushed, listed or shown on Today,
until the shadow review has covered at least 20 pledge items with at least 95% correct symbols.
Reasons: the encumbrance feed also carries releases and invocations, its items have no link and
no date (so the symbol comes only from a name match), and the 30-day dedupe bucket can store one
disclosure twice. When the bar is met, add `'pledge'` to `event_radar.USER_VISIBLE_TYPES` and
`today_service.TODAY_EVENT_TYPES` in one reviewed change. The push copy for pledges is already
neutral ("filed a disclosure about encumbered promoter shares").

**Watchlist v2 full version**: `watchlists` and `watchlist_items` with a default list, named
lists and server tags. It waits for three things:

- the money cluster's C4 ledger migration of portfolio rows;
- a resolution of the Skeptic's named-list objection;
- I47 evidence of daily return use.

## 5. Data sources and terms

Event Radar reads three NSE public RSS feeds:

| Feed | URL |
|---|---|
| announcements | `https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml` |
| board_meetings | `https://nsearchives.nseindia.com/content/RSS/Board_Meetings.xml` |
| encumbrance | `https://nsearchives.nseindia.com/content/RSS/Sast_ReasonForEncumbrance.xml` |

- **Honest client.** User-Agent `NiveshEvents/1.0 (+RESEARCH_HTTP_CONTACT)`, where the value of
  `RESEARCH_HTTP_CONTACT` in `backend/.env` is an email or URL. If it is unset, nothing is
  fetched and a CRITICAL is logged once. No browser user agents, no proxies.
- **Polling.** Every 5 minutes, 07:00-23:55 IST, every day (the feeds declare `<ttl>5</ttl>`),
  about 600 requests a day across the three feeds. Conditional GET (ETag / If-Modified-Since),
  15 s timeout, 30-minute back-off after 3 consecutive failures.
- **Feed window.** Each feed holds about 25 items and can roll over at peak times. Watch the
  logs for `event_radar feed window saturated: <feed>` warnings; repeated warnings mean filings
  are being missed between polls.
- **If NSE blocks the client, never disguise it.** Stop (set `event_radar=off`) and move to a
  licensed filings vendor.
- **Review query**, run on the server:

  ```sql
  SELECT symbol, event_type, severity, title, source_url, published_at FROM stock_events ORDER BY published_at DESC LIMIT 50;
  ```

  Compare each row with its NSE filing (open `source_url`). Count a row correct only when both
  `symbol` and `event_type` match the filing. For the pledge bar in section 4, run the same
  query with `WHERE event_type = 'pledge'` and check symbols against the NSE encumbrance page.

## 6. Privacy and delivery rules

- **Push bodies contain no ₹ amounts.** They show on the lock screen. Today and the widget
  honour "Hide portfolio values" ("₹ ••••").
- **At most 8 automatic notifications a day**: daily brief, filings and results reminders
  together, counted from local midnight in the user's time zone. Per-category caps: daily brief
  1, filings 3, results reminders 5. Price alerts the user set are limited only by their own cap
  of 20 a day.
- **Quiet hours** apply to every category except the daily brief: they do not hold back the
  daily brief, because the user chose its time. Suppressed pushes still land in the inbox.
- **Retention.** Inbox and delivery rows are kept for 14 days. `stock_events` rows are kept for
  180 days (job `habit_events_prune`).
- **Pledge rows store no summary**, because the feed names individual promoters.
- **Erasure** is covered by existing `ERASURE_POLICY` entries: new user-linked data lives only in
  `user_preferences`, `in_app_notifications` and `portfolio`. `stock_events` holds only public
  exchange data.
- **Export.** The export (platform cluster) must include notification prefs, inbox rows and
  `portfolio.added_price`.
- **Privacy policy** must mention APNs delivery (notification content goes through Apple Push
  Notification service) and the use of public NSE filings, plus server-side notification
  preferences and the 14-day inbox and delivery log.
- **Logs** carry only user_id, category and outcome: no bodies, no tokens.

## 7. Jobs (IST)

Registered by `services/habit_jobs.register_habit_jobs(scheduler)` from
`harvest_worker.start_scheduler`, so they run on the scheduler leader only. All jobs use
`max_instances=1`, `coalesce=True`, `replace_existing=True`. Flags are checked inside each job,
not at registration. Failures are logged and sent to
`error_telemetry.log_diagnostic_error(subsystem="HABIT")` and never stop other jobs.

| Job id | Schedule (IST) | Runs when | Calls |
|---|---|---|---|
| `habit_event_cycle` | every 5 minutes, 07:00-23:55, daily | `event_radar` is shadow or on | `event_radar.run_event_cycle()` |
| `habit_earnings_reminders` | 18:00 daily | `notif_prefs_v2` is on | `alerts_service.send_earnings_reminders()` |
| `habit_brief_push` | every 15 minutes, all day, every day | `today_brief` is on | `today_service.run_brief_push()`; each user's own time zone and weekday are checked in code (`due_brief_users`) |
| `habit_events_prune` | Sunday 03:30 | always | `event_radar.prune_events()` (older than 180 days) |

Results reminders go out for saved results dates that fall tomorrow (IST). The brief push goes
out on the user's local weekdays, from their chosen time through a 3-hour catch-up window, and
is skipped when the engine data is not fresh.

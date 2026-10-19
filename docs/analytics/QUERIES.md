# Product analytics queries

Postgres SQL over `user_events` (see `services/events_service.py` for the ten allowlisted events).

Read this first:

- Only users who turned on the `product_analytics` consent are counted, so every number is a sample of the consenting users, not of all users. App Store Connect analytics is the unbiased baseline.
- Turning the consent off deletes that user's events immediately, and the daily retention job deletes anything older than `USER_EVENTS_RETENTION_DAYS` (180 by default) or left behind without a consent. Withdrawn users therefore never appear.
- Props never hold tickers, amounts or free text. `created_at` is the client's event time in naive UTC (clamped to 7 days back and 5 minutes forward), so convert to IST for day boundaries.

## Daily and weekly active users

```sql
-- DAU by IST date
SELECT (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date AS day,
       COUNT(DISTINCT user_id) AS dau
FROM user_events
WHERE created_at >= now() AT TIME ZONE 'UTC' - interval '30 days'
GROUP BY 1 ORDER BY 1;

-- WAU: distinct users per ISO week
SELECT date_trunc('week', created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date AS week,
       COUNT(DISTINCT user_id) AS wau
FROM user_events
GROUP BY 1 ORDER BY 1;
```

## D1 / D7 / D30 retention from first app_open

```sql
WITH first_open AS (
  SELECT user_id, MIN((created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date) AS d0
  FROM user_events WHERE event_name = 'app_open' GROUP BY user_id
), activity AS (
  SELECT DISTINCT user_id, (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date AS day
  FROM user_events
)
SELECT f.d0 AS cohort_day,
       COUNT(*) AS users,
       COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM activity a WHERE a.user_id = f.user_id AND a.day = f.d0 + 1))  AS d1,
       COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM activity a WHERE a.user_id = f.user_id AND a.day = f.d0 + 7))  AS d7,
       COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM activity a WHERE a.user_id = f.user_id AND a.day = f.d0 + 30)) AS d30
FROM first_open f
GROUP BY f.d0 ORDER BY f.d0;
```

Divide `d1`, `d7`, `d30` by `users` for the rate. Cohorts younger than 1, 7 or 30 days are incomplete.

## Funnel: search, stock_view, report_view

```sql
SELECT COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'search')      AS searched,
       COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'stock_view')  AS viewed_stock,
       COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'report_view') AS viewed_report
FROM user_events
WHERE created_at >= now() AT TIME ZONE 'UTC' - interval '30 days';
```

For a strict ordered funnel per user, join each step to the earliest earlier step by `created_at`.

## Funnel: paywall_view to purchase

```sql
SELECT COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'paywall_view') AS saw_paywall,
       COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'purchase' AND props->>'outcome' = 'success') AS purchased
FROM user_events
WHERE created_at >= now() AT TIME ZONE 'UTC' - interval '30 days';
```

## report_compute outcome mix

```sql
SELECT props->>'result' AS result, COUNT(*) AS n
FROM user_events
WHERE event_name = 'report_compute'
  AND created_at >= now() AT TIME ZONE 'UTC' - interval '30 days'
GROUP BY 1 ORDER BY n DESC;
```

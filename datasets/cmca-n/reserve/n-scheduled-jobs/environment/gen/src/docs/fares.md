# Fares

## 1. Minutes

1.1 Every started minute is billed: a trip of 0 seconds is 0 minutes, 1 to 60
seconds is 1 minute, 61 to 120 seconds is 2 minutes, and so on.
`spokehouse.fares.billable_minutes(seconds)` gives that number.

1.2 Durations come from `end` minus `start` of the trip record (`jobs.md`
2.1), so a trip that crosses a change of the local clock is billed for the
time it really took.

## 2. Plans

| Plan | Fare in cents |
|---|---|
| `monthly` | 15 per billable minute after the first 30 (`INCLUDED_MINUTES`) |
| `payg` | 100 to unlock, plus 20 per billable minute |

Examples: a monthly trip of 30 minutes 0 seconds costs 0; of 30 minutes 1
second, 15; of 42 minutes 0 seconds, 180. A payg trip of 9 minutes 10 seconds
is 10 minutes: 300.

The rates are in `spokehouse/settings.py`.

# Recurrence rules

An event repeats when its file has an `rrule`. The rule is written in the
`RRULE` syntax of RFC 5545 and the package supports the subset below. Where
this note and the RFC differ, this note wins.

## 1. Terms

1.1 The **event start** is the `start` of the event file, a local wall time in
the event's zone (`events.md` 3.1).

1.2 A **period** is one day, week, month or year, depending on FREQ. Periods
are counted from the one that holds the event start, which is period 0.

1.3 A **generated time** is a local wall time the rule produces. All generated
times have the time of day of the event start; the package supports no
BYHOUR, BYMINUTE or BYSECOND part.

## 2. Syntax

2.1 A rule is a list of `NAME=VALUE` parts separated by `;`. Names are upper
case. Each name appears at most once. Parts may come in any order.

2.2 Supported parts:

| Part | Values | Default |
|---|---|---|
| `FREQ` | `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY` | required |
| `INTERVAL` | 1 to 1000 | 1 |
| `COUNT` | 1 to 10000 | none |
| `UNTIL` | `YYYYMMDD` or `YYYYMMDDTHHMMSSZ` | none |
| `BYDAY` | comma list of `MO` to `SU`, each with an optional signed number | none |
| `BYMONTHDAY` | comma list of 1 to 31 and -1 to -31 | none |
| `BYMONTH` | comma list of 1 to 12 | none |
| `BYSETPOS` | comma list of 1 to 366 and -1 to -366 | none |
| `WKST` | `MO` to `SU` | `MO` |

2.3 A list holds no value twice. Zero is never a valid number. A `+` sign is
allowed and means the same as no sign.

2.4 Any other part (`BYHOUR`, `BYWEEKNO`, `BYYEARDAY`, `FREQ=HOURLY` and so on)
makes the rule unsupported, which is an error for the event.

## 3. Combinations that are errors

3.1 `COUNT` and `UNTIL` together.

3.2 `BYMONTHDAY` with `FREQ=WEEKLY`.

3.3 A numbered `BYDAY` entry (`2TU`, `-1FR`) with `FREQ=DAILY` or
`FREQ=WEEKLY`, or with `FREQ=YEARLY` when the rule has no `BYMONTH`. A
numbered entry counts weekdays within a month, so its number is 1 to 5 or -1
to -5.

3.4 `BYSETPOS` with `FREQ=DAILY` or `FREQ=WEEKLY`, or without any `BYDAY` or
`BYMONTHDAY`.

## 4. Expanding a period

4.1 For each period the rule gives a set of dates. A date that does not exist
(30 February, 31 April, 29 February outside a leap year) is never in the set;
it is skipped, not moved to a nearby day.

4.2 **DAILY.** Period k is the day that lies k x INTERVAL days after the event
start date. Its set is that day, unless `BYMONTH`, `BYMONTHDAY` or `BYDAY`
leave it out: each one present must accept the day.

4.3 **WEEKLY.** A week begins on the WKST weekday. Period 0 is the week that
holds the event start date; period k begins k x INTERVAL weeks after the
first day of period 0. Its set is the days of that week whose weekday is in
`BYDAY` (the weekday of the event start when `BYDAY` is absent), less any day
whose month is not in `BYMONTH` when `BYMONTH` is present. WKST matters only
when INTERVAL is above 1: it decides which days belong to the same week, and
so which weeks are skipped.

4.4 **MONTHLY.** Period k is the month that lies k x INTERVAL months after the
month of the event start. When `BYMONTH` is present and does not list that
month, the set is empty. Otherwise the set is, within that month:

- with `BYMONTHDAY` and `BYDAY`: the days both of them give (4.6);
- with `BYMONTHDAY` only: the days it gives;
- with `BYDAY` only: the days it gives;
- with neither: the day of the month of the event start.

4.5 **YEARLY.** Period k is the year that lies k x INTERVAL years after the
year of the event start. The months of the period are those in `BYMONTH`; with
no `BYMONTH`, all twelve when the rule has `BYDAY` or `BYMONTHDAY`, otherwise
only the month of the event start. Each month gives days as in 4.4, and the set
is all of them.

4.6 Within a month, `BYMONTHDAY=n` gives day n; a negative n counts from the
end of the month, so -1 is the last day and -2 the day before. `BYDAY=WE`
without a number gives every Wednesday of the month. `BYDAY=2WE` gives the
second Wednesday; `BYDAY=-1WE` gives the last Wednesday and `-2WE` the one
before it. A numbered entry that the month does not reach (`5MO` in a month
with four Mondays) gives no day. The days a `BYDAY` list gives are the union
of the days each of its entries gives.

4.7 **BYSETPOS.** After the set of a period is known, `BYSETPOS` keeps only the
dates at the listed positions of the set sorted in time order: 1 is the first
date of the set, -1 the last. Positions beyond the size of the set keep
nothing.

4.8 The generated times of a period are its dates at the time of day of the
event start, in time order. Periods are walked in order: period 0, 1, 2 and so
on. Generated times at or before the event start are dropped.

## 5. The event start, COUNT and UNTIL

5.1 The event start is always the first generated time, even when the rule
would not produce it (an event that starts on a Tuesday with
`FREQ=WEEKLY;BYDAY=MO` has its first instance on that Tuesday and the next
ones on Mondays).

5.2 `COUNT=n` keeps the first n generated times, the event start included.
It is counted before excluded dates are taken out (`events.md` 4.2): an
`exdate` that removes a generated time does not make the rule produce another
one in its place. Extra dates (`rdate`) are not generated times and never
count.

5.3 `UNTIL` is inclusive: a generated time equal to UNTIL is kept, and the rule
stops at the first generated time after it. The event start is kept even when
it is after UNTIL (5.1).

5.4 `UNTIL=YYYYMMDD` is a local date: a generated time is after it when its
local date is a later day.

5.5 `UNTIL=YYYYMMDDTHHMMSSZ` is an instant in UTC: a generated time is after it
when the time, turned into UTC with the event's zone (`zones.md` section 4),
is later than that instant. The local wall time is never compared with the
UTC digits directly.

5.6 A rule with neither COUNT nor UNTIL never ends. The package expands it as
far as the window and the overrides of the event need (`events.md` 5.4); how
far it looks is not visible in any document.

# Events

## 1. Scope

1.1 This note covers event files, extra and excluded dates, overrides,
durations and the reporting window. Recurrence rules are in `rules.md`; zones
and the handling of skipped and repeated local times are in `zones.md`.

## 2. Time formats

2.1 A **local time** is written `YYYY-MM-DDTHH:MM` with no zone suffix and no
seconds, for example `2027-03-14T09:30`. It is a wall time in the event's
zone.

2.2 A **UTC time** is written `YYYY-MM-DDTHH:MMZ`, for example
`2027-03-14T08:30Z`.

2.3 A **recurrence id** is the local time that names an instance: the
generated time for an instance of the rule, the event start for the first
instance, the listed time for an extra date. It is the time as written or
generated, before any skipped-time shift (`zones.md` 4.2) and before any
override moves the instance. Excluded dates and overrides find their instance
by recurrence id.

## 3. Event files

3.1 An event file has these keys:

| Key | Required | Meaning |
|---|---|---|
| `uid` | yes | `EV-` followed by at least four digits; the file name without `.json` |
| `summary` | no | a title, copied to the documents |
| `zone` | yes | a zone name of `zones.json` |
| `start` | yes | the event start, a local time |
| `duration_min` | yes | whole minutes, 1 to 10080 |
| `rrule` | no | a recurrence rule (`rules.md`); without it the event has one generated time, its start |
| `rdate` | no | list of extra dates, local times |
| `exdate` | no | list of excluded dates, local times |
| `overrides` | no | list of overrides (section 5) |

3.2 A file whose `uid` is not its file name is an error.

## 4. Excluded and extra dates

4.1 The recurrence ids of an event are its generated times, kept up to COUNT
(`rules.md` 5.2), less its excluded dates, plus its extra dates that are not
excluded.

4.2 An excluded date removes the instance whose recurrence id equals it. An
excluded date that equals no recurrence id does nothing and is not an error.
An excluded date can remove the event start and can remove an extra date.

4.3 An extra date adds an instance with that recurrence id. Extra dates are not
limited by COUNT or UNTIL and may come before the event start.

4.4 An event has at most one instance per recurrence id. An extra date equal to
a generated time, or listed twice, is the same instance and appears once.

## 5. Overrides

5.1 An override has:

| Key | Required | Meaning |
|---|---|---|
| `recurrence_id` | yes | the recurrence id of the instance it changes |
| `start` | no | the new local start of the instance |
| `duration_min` | no | the new duration of the instance |
| `cancelled` | no | `true` removes the instance; default `false` |

5.2 An override that is not cancelled changes the start, the duration or both.
One that changes neither is an error. A cancelled override has no `start` and
no `duration_min`; one that has either is an error. Two overrides with the
same recurrence id are an error.

5.3 An override applies to the instance with its recurrence id after excluded
and extra dates are settled (section 4). An override whose recurrence id is not
a recurrence id of the event does nothing and is not an error: it does not add
an instance.

5.4 A moved instance keeps its recurrence id. It can move anywhere: earlier or
later than other instances, out of the window, or into the window from a
recurrence id far outside it. The window test (section 7) uses the instance as
it stands after its override.

5.5 An instance that an override changes is marked as overridden in the
documents (`output.md` 2.2), whether or not its values differ from the
original ones.

## 6. Durations

6.1 Every instance lasts the duration of its override when it has one, and the
`duration_min` of the event otherwise.

6.2 A duration is elapsed time. The end of an instance is its UTC start plus
the duration, so an instance always lasts exactly its duration in UTC. When a
daylight saving change falls inside an instance, its local end differs from
its local start plus the duration: a 120-minute instance that starts at 01:00
on the night the clocks move forward one hour at 02:00 ends at 04:00 local.

## 7. The reporting window

7.1 `DATA/agenda.json` has `from` and `to`, both dates written `YYYY-MM-DD`,
with `to` after `from`. The window runs from 00:00 UTC on `from` to 00:00 UTC
on `to`; the start is inside the window, the end is not.

7.2 An instance is listed when it overlaps the window: its UTC start is before
the end of the window and its UTC end is after the start of the window. An
instance that started before the window and is still running at its start is
listed.

7.3 An event with no instance in the window gets a document with an empty
instance list. That is not an error.

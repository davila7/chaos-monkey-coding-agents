# Zones

Events carry local wall times. The zone table in `DATA/zones.json` says how a
local time in each zone relates to UTC. It is the only source of zone rules;
the system time zone database is never read (`overview.md` 1.4).

## 1. The zone table

1.1 `zones.json` is an object keyed by zone name. Each zone has:

| Key | Required | Meaning |
|---|---|---|
| `std_offset_min` | yes | standard offset from UTC in minutes, -720 to 840 |
| `dst` | no | the daylight saving period; a zone without it keeps its standard offset all year |

1.2 `dst` has:

| Key | Required | Meaning |
|---|---|---|
| `offset_min` | yes | offset from UTC in minutes while daylight saving is in force; it differs from the standard offset |
| `start` | yes | the yearly change from the standard offset to the daylight saving offset |
| `end` | yes | the yearly change back to the standard offset |

1.3 Offsets are positive east of UTC: a zone at `std_offset_min` 60 shows
10:00 when UTC is 09:00. Offsets need not be whole hours, and the daylight
saving offset need not be one hour away from the standard offset.

1.4 A zone that breaks this note is an error for every event in it.

## 2. Changes

2.1 A change (`start` or `end`) has:

| Key | Required | Meaning |
|---|---|---|
| `month` | yes | 1 to 12 |
| `week` | yes | `"1"` to `"4"` for the first to fourth such weekday of the month, `"last"` for the last one |
| `weekday` | yes | `MO` to `SU` |
| `time` | yes | `HH:MM`, 00:00 to 23:59 |
| `basis` | no | `wall` (default) or `utc` |

2.2 With `basis` `utc`, `time` is the UTC time of the change on that day. With
`basis` `wall`, `time` is the local time shown by the zone just before the
change: the standard time for `start` and the daylight saving time for `end`.

2.3 In each year the change of `start` and the change of `end` each happen once,
at the instant 2.2 gives.

## 3. Which offset is in force

3.1 When `start` comes before `end` in the year (zones north of the equator),
daylight saving is in force from the instant of `start` to the instant of
`end` of the same year: the start instant is inside, the end instant is not.

3.2 When `start` comes after `end` in the year (zones south of the equator),
daylight saving is in force from the instant of `start` to the instant of
`end` of the next year. Within one calendar year, it is in force before the
instant of `end` and from the instant of `start` on.

3.3 At every other instant the standard offset is in force.

## 4. From a local time to UTC

4.1 A local time names one instant when exactly one offset of the zone turns it
into an instant at which that same offset is in force. That instant is its
UTC time.

4.2 **Skipped times.** When the clocks move forward, the local times of the
gap do not exist (with a change at 02:00 to an offset one hour later, 02:00 to
02:59 are skipped). A skipped local time is read with the offset in force just
before the change, so it lands after the change: 02:30 in a one-hour gap
becomes 03:30 in the new offset. It is never moved back to before the change.

4.3 **Repeated times.** When the clocks move back, the local times of the
overlap happen twice (with a change at 03:00 back to 02:00, 02:00 to 02:59 are
shown twice). A repeated local time means its first occurrence, the one with
the offset in force before the change.

4.4 These rules apply to every local time in an event file that becomes an
instant: generated times, extra dates and the start of an override. They do not
change recurrence ids, which stay as written or generated (`events.md` 2.3).

## 5. From UTC to a local time

5.1 A UTC instant is shown in a zone by adding the offset in force at that
instant. The documents show local start and end times this way
(`output.md` 2.2), so the local start of an instance whose generated time was
skipped is the shifted time, not the generated one.

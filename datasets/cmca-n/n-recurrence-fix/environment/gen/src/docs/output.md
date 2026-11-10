# Output

## 1. Event documents

1.1 Each event that can be expanded gets one document. Its keys, in this
order:

| Key | Meaning |
|---|---|
| `uid` | the event uid |
| `summary` | the summary of the event file, `""` when it has none |
| `zone` | the zone name |
| `rule` | the `rrule` text exactly as written, or `null` |
| `instances` | the instances in the window, sorted (section 2) |

## 2. Instances

2.1 The instances of a document are sorted by their UTC start; instances with
the same UTC start are sorted by recurrence id. The order is the order in time
after overrides, not the order of the recurrence ids.

2.2 Each instance has these keys, in this order:

| Key | Meaning |
|---|---|
| `recurrence_id` | the recurrence id, a local time (`events.md` 2.3) |
| `start` | the local start: the UTC start shown in the zone (`zones.md` 5.1) |
| `end` | the local end: the UTC end shown in the zone |
| `start_utc` | the UTC start |
| `end_utc` | the UTC end |
| `offset` | the offset in force at the UTC start, written `+HH:MM` or `-HH:MM` |
| `overridden` | `true` when an override applies to the instance, otherwise `false` |

2.3 Times are written in the formats of `events.md` section 2.

## 3. The agenda listing

3.1 `run` writes `OUT/agenda.json`: a list with one row per instance of every
expanded event. Each row has `start_utc`, `end_utc`, `uid` and
`recurrence_id`, in this order, with the values of the instance.

3.2 Rows are sorted by `start_utc`, then `uid`, then `recurrence_id`.

## 4. The text view

4.1 `show` prints a header line with the uid, the summary and the zone in
parentheses, a line `rule: ` with the rule text or `none`, one line per
instance with its local start, its offset and its local end (date and time
separated by a space, an ` *` after overridden instances), and a last line
with the number of instances.

## 5. Errors

5.1 `run` writes `OUT/errors.json`: a list of objects with `event` (the uid
taken from the file name) and `error` (the error class name, a colon, a space
and a message). It is sorted by uid. An empty list is written when every event
could be expanded.

5.2 The error classes are `ZoneError` (an unknown zone or a broken zone),
`RuleError` (a rule that breaks `rules.md`) and `EventError` (anything else in
an event file that breaks `events.md`).

# Feeds

## 1. Files

A feed file is JSON lines: a header, then one record per line.

```
{"batch": "T020114", "count": 3, "delivered": "2027-03-27T04:14:37+00:00", "kind": "trips"}
{"end": "2027-03-27T04:09:49+00:00", "from": "D04", "member": "M1023", "start": "2027-03-27T03:21:49+00:00", "to": "D04", "trip": "R880442"}
...
```

- `kind` is `trips`, `holds` or `rebalance`; `count` is the number of records.
- trips records: `trip`, `member`, `from`, `to`, `start`, `end`.
- holds records: `hold`, `member`, `dock`, `until`.
- rebalance records (a truck manifest): `from`, `to`, `bikes`.

The scheduler names the file each run reads in its start line (`operations.md`
2). A file under `feeds/` is the exact bytes the run read.

## 2. Times

The trip system and the member app write times in the local time of the city
with its offset, for example `2027-03-27T10:40:00+00:00` in winter and
`2027-03-29T10:40:00+01:00` in summer. Other deployments use other offsets,
and a feed may also carry UTC times with `Z`. Code reads them with
`spokehouse.timeutil.parse_ts` and compares the results (`overview.md` 3).

## 3. Bad files

A file whose header is missing or wrong, whose `count` does not match, or with
a line that is not JSON is refused whole with `FeedError` (`jobs.md` 1.2). The
trip system sends a refused batch again, with the same id, at the next run.

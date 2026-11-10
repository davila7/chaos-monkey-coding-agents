# Logger clocks

## 1. Logger time zones

1.1 A logger clock runs on a fixed offset from UTC, with no daylight saving
time. The `tz` directive of a file gives it: `Z` for UTC, or a sign, hours
and minutes, `+HH:MM` or `-HH:MM`. Offsets need not be whole hours
(`+05:30`, `-03:30`).

1.2 The logger UTC instant of a logger time is the logger time minus the
offset: 10:00:00 at `+02:00` is 08:00:00 UTC, 10:00:00 at `-03:30` is
13:30:00 UTC.

1.3 Every row and every sync line uses the `tz` of its own file. A logger can
be set to another time zone between two uploads, so two files of one station
can state different `tz` values, and the same reading can appear in both
with different logger times.

## 2. Clock drift

2.1 Logger clocks gain or lose a few seconds a day. When a logger reaches the
network time service it writes a sync line (`files.md` 7): `logger=` is what
its clock showed at that moment, and `ref=` is the true UTC time at the same
moment. The logger does not set its clock from it; a sync line is a
comparison only.

2.2 The offset at a sync point is `ref` minus the logger UTC instant of
`logger=`, in whole seconds. It can be negative. In the example of `files.md`
the logger time 09:12:41 at `+01:00` is 08:12:41 UTC and `ref` is 08:12:03,
so the offset is -38 seconds.

2.3 The sync points of a station are collected from all of its files. A sync
point that appears in several files (overlapping or reissued uploads) counts
once; it is identified by its logger UTC instant, and if two files disagree
on its `ref`, the file with the larger upload number is right.

2.4 The clock offset at a logger UTC instant `t`:

- At a sync point, the offset of that sync point.
- Between two consecutive sync points `(t1, o1)` and `(t2, o2)`, with
  `t1 < t < t2`: `o1 + (o2 - o1) * (t - t1) / (t2 - t1)`, rounded down to a
  whole second. Rounded down means toward negative infinity, also when the
  result is negative: -12.4 becomes -13.
- Before the first sync point of the station, the offset of the first sync
  point; after the last, the offset of the last. Offsets are never
  extrapolated.
- A station without any sync point has offset 0 everywhere.

2.5 The corrected time of a row is its logger UTC instant plus the clock
offset at that instant. Hours (`aggregation.md` 1), the order of rain
readings (`aggregation.md` 5) and the range of hours of a station
(`output.md` 2.2) all use corrected times.

## 3. Repeated rows

3.1 Dumps overlap, because a logger sends again what it is not sure was
received, and a logger can reissue a period with corrected values. Two rows of
one station with the same logger UTC instant are the same sample.

3.2 Of the rows of one sample, only the row from the file with the largest
upload number is kept. It is kept as a whole: its missing values stay
missing, even where an older file had a value. The other rows of the sample
are dropped.

3.3 Repeated rows are found by logger UTC instant, not by the logger time as
written, since files of one station can use different `tz` values (rule 1.3).

# Hourly values

## 1. Hours

1.1 An hour is named by the UTC time at which it ends. Hour `H` holds the
corrected times after `H` minus one hour, up to and including `H`. A reading
with corrected time 10:00:00 belongs to hour 10:00; one at 10:00:01 belongs
to hour 11:00; one at 09:00:00 belongs to hour 09:00.

1.2 Hours are always on UTC, whatever the `tz` of the files.

## 2. Coverage

2.1 For each station, hour and quantity, `n` is the number of readings of
the quantity in the hour (rows kept after `clock.md` 3, values not missing,
inside the valid range). The expected count of an hour is 3600 divided by
the interval of the station.

2.2 The hourly value of a quantity is reported only when coverage is enough:
`n` must be at least 75 percent of the expected count, that is `n * 4 >= expected * 3`; otherwise the value is null and `n` is still reported.

2.3 Drift correction can move a sample into the next or previous hour, so an
hour can hold one reading more or less than the expected count. That changes
nothing in rule 2.2.

## 3. Means

3.1 The hourly value of `temp`, `rh`, `pres` and `wspd` is the arithmetic
mean of the readings of the hour, in the canonical unit.

## 4. Wind direction

4.1 The hourly value of `wdir` is a vector mean, never an arithmetic mean of
the angles: each reading of `wdir` whose row also has a reading of `wspd`
greater than 0 gives a unit vector pointing to its direction. The hourly
direction is the direction of the sum of these vectors, in degrees clockwise
from north, from 0 up to but not including 360. Wind speeds do not weight the
vectors.

4.2 `n` of `wdir` counts every reading of `wdir` of the hour, calm samples
and samples without a `wspd` reading included. Coverage (rule 2.2) is
checked on that `n`.

4.3 When coverage is enough but no reading of the hour gives a vector (every
sample calm or without a `wspd` reading), the value is null.

## 5. Rain

5.1 A rain gauge reports a counter that grows with each tip of its bucket and
goes back to 0 when the logger restarts. The hourly value of `rain` is the
precipitation of the hour in millimetres, worked out from the increments of
the counter.

5.2 The readings of `rain` of a station are taken in corrected time order.
For each reading `r` with a previous reading `p`, if the corrected times of
`p` and `r` are at most 2.5 intervals apart, `r` has an increment:
`r - p` when `r >= p`, and `r` itself when `r < p` (the counter restarted at 0
since `p`). A reading without a previous reading, or with one that is more
than 2.5 intervals before it, has no increment: what fell during the gap is
not known.

5.3 Missing and out of range values are not readings, so `p` is the last
reading before `r`, however many rows without a rain reading lie between.

5.4 The hourly value is the sum of the increments of the readings in the
hour. `n` counts the readings of the hour, with or without an increment, and
coverage is rule 2.2. An hour with enough coverage and no rain has the value
0.

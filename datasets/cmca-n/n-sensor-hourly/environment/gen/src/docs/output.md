# The hourly file

## 1. Shape

1.1 The hourly file is one JSON object:

    {
      "stations": [
        {
          "station": "KV07",
          "interval_s": 300,
          "hours": [
            {
              "hour": "2027-01-14T09:00:00Z",
              "temp": {"value": -2.04, "n": 12},
              "rh": {"value": 91.25, "n": 12},
              "pres": {"value": 1006.17, "n": 12},
              "wspd": {"value": null, "n": 7},
              "wdir": {"value": 217.36, "n": 11},
              "rain": {"value": null, "n": 0}
            }
          ]
        }
      ]
    }

1.2 Layout, indentation and key order are free; the file is read as JSON.
Extra keys are not allowed.

## 2. Stations and hours

2.1 `stations` holds one entry per station that has at least one data row in
the input, in text order of the station id. `station` is the id as written in
the `station` directive and `interval_s` the interval of the station as a
whole number.

2.2 `hours` holds every hour from the hour of the station's earliest
corrected time to the hour of its latest, in time order, one entry each,
including hours with no rows at all. Every kept row counts for this range,
also a row whose values are all missing.

2.3 `hour` is the name of the hour (`aggregation.md` 1), written
`YYYY-MM-DDTHH:00:00Z`.

2.4 Every hour entry has all six quantities of `quantities.md` 1, also those
the station does not report: they have `{"value": null, "n": 0}`.

## 3. Values

3.1 `n` is a whole number. `value` is a number in the canonical unit, or
null (`aggregation.md`).

3.2 Values are rounded to 2 decimals. A direction that rounds to 360.00 is
written as 0.0.

3.3 The forecasting system compares values to 0.01: two hourly files agree
when every `n` and every null is the same and every value differs by at most
0.01 (directions around the circle, so 359.99 and 0.0 differ by 0.01).

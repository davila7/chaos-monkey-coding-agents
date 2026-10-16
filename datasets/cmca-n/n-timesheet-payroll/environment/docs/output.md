# Payroll summary format

`payroll.py INPUT_DIR OUTPUT_FILE` writes one JSON object to `OUTPUT_FILE`:

    {
      "period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
      "employees": {
        "<employee_id>": {
          "shifts": <int>,
          "paid_minutes": <int>,
          "overtime_minutes": <int>,
          "night_minutes": <int>,
          "gross": "<decimal string with exactly two decimals>"
        },
        ...
      },
      "exceptions": {
        "open_shifts": <int>,
        "orphan_outs": <int>,
        "duplicates_dropped": <int>,
        "corrections_applied": <int>
      },
      "totals": {
        "shifts": <int>,
        "paid_minutes": <int>,
        "overtime_minutes": <int>,
        "night_minutes": <int>,
        "gross": "<decimal string with exactly two decimals>"
      }
    }

- `period` repeats `start` and `end` from `period.json`.
- `employees` has one entry for every row of `employees.csv`, with zeros and `"0.00"` for employees
  without shifts in the period. Per employee: `shifts` is the number of shifts (step 5) whose
  workday is in the period, the minute fields are the sums over those shifts (steps 7 and 8), and
  `gross` is step 9.
- `exceptions`: `open_shifts`, `orphan_outs` and `duplicates_dropped` count those whose workday is
  in the period (step 6); `corrections_applied` counts every correction that was applied (step 2),
  whatever its punch's date.
- `totals`: the sums of the employee values; `gross` is the sum of the employees' rounded gross.
- Numbers are JSON integers; amounts are strings such as `"1234.50"`. Key order and whitespace do not
  matter.

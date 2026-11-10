# Rounding in one place

Status: agreed, ready to implement. Owner: billing team.

## 1. Why

Every module of `meterbill` that produces an amount rounds it on its own:
`tariffs`, `standing`, `tax`, `cash` and `credits` each carry their own
`CENT` or their own arithmetic, and `report` rounds again when it writes
figures. Some of these roundings depend on process state (section 4). The
next tariff change needs one place where the rounding rules live and can be
read.

This is a refactor. No figure that `meterbill` prints may change, for any
input. If something looks like a bug, keep it as it is and say so in your
summary; fixing it is a separate change.

## 2. The module

Create `meterbill/money.py` with exactly these public names:

```python
CENT = Decimal("0.01")
HALF_UP = "half_up"
HALF_EVEN = "half_even"
DOWN = "down"

def round_amount(value: Decimal, step: Decimal, method: str) -> Decimal: ...
def allocate(amounts: list[Decimal], step: Decimal) -> list[Decimal]: ...
def legacy_cents(value: float, places: int = 2) -> float: ...
def fixed(value: float | Decimal, places: int, method: str = HALF_EVEN) -> str: ...
```

Helpers it needs start with `_`. `money.py` imports nothing from `meterbill`.

### 2.1 `round_amount`

The multiple of `step` nearest to `value`. `method` decides ties and
direction:

- `HALF_UP`: a tie goes away from zero.
- `HALF_EVEN`: a tie goes to the even multiple of `step`.
- `DOWN`: toward zero, no tie rule.

The result carries the exponent of `step`: `round_amount(Decimal("7"),
Decimal("0.05"), HALF_UP)` is `Decimal("7.00")`, and with `Decimal("1")` the
result has no fraction digits. `step` may be any positive decimal (`0.01`,
`0.05`, `0.10`, `1`, `0.0001`). `value` and `step` must be `Decimal`
(`TypeError` otherwise); an unknown `method` or a `step` that is not positive
raises `ValueError`.

### 2.2 `allocate`

The split that `standing.prorate` makes today, for any list of amounts:
one part per amount, each a multiple of `step`, adding up to
`round_amount(sum(amounts), step, HALF_UP)`. Read `standing.prorate` for
how the parts are cut and where the difference goes. The input list is not
changed; an empty list gives an empty list.

### 2.3 `legacy_cents`

What `credits.settle` does today, for any float and any `places` from 0 to
6 (`places=2` is `settle`). It stays binary floating point on purpose: these
amounts come from the old customer system and must settle exactly as that
system settled them.

### 2.4 `fixed`

The text of `value` with `places` digits after the point (no point when
`places` is 0), rounded by `method`.

- A `float` is written as Python's own formatting writes it
  (`format(value, ".2f")`): its exact binary value rounded half to even.
  Any other `method` with a float raises `ValueError`.
- A `Decimal` is `round_amount(value, step, method)` written out in full,
  where `step` is `10 ** -places`; never in exponent notation.

## 3. Where the code rounds today

We found these by searching for `quantize` and `round(`:

| Site | Today | In `money` terms |
|---|---|---|
| `tariffs.charge_bands`, each band | `quantize(CENT)` | `round_amount(..., CENT, ...)`, method: section 4 |
| `standing.prorate`, each segment | `quantize(CENT, ROUND_DOWN)`, remainder to a segment | `allocate(amounts, CENT)` |
| `standing.prorate`, the whole | `quantize(CENT, ROUND_HALF_UP)` | inside `allocate` |
| `tax.vat` | `quantize(CENT, ROUND_HALF_EVEN)` | `round_amount(..., CENT, HALF_EVEN)` |
| `cash.payable`, rule `0.05` and other steps | `(total / step).quantize(1, ROUND_HALF_UP) * step` | `round_amount(total, step, HALF_UP)` |
| `cash.payable`, rule `whole` | `Decimal(round(total))` | `round_amount(total, Decimal("1"), HALF_EVEN)` |
| `credits.settle` | `math.floor(amount * 100 + 0.5) / 100` | `legacy_cents(amount)` |
| `report.bill_json`, `average_per_day` | `round(x, 2)` on a float | via `fixed` |

The search does not find roundings that are not spelled `quantize` or
`round(`. Section 5, rule 1, says what counts.

## 4. The decimal context

`meterbill/__init__.py` sets the rounding of the decimal context when the
package is imported. Any `quantize` without a `rounding=` argument, and any
other decimal operation that rounds by the context, depends on that line and
on where the code runs. This is the process state the refactor removes:
delete that line, and give every site that depends on the context today the
method it actually uses today, on every path that reaches it (`bill`,
`quote`, `batch`, `tariffs`). If two paths round the same site differently
today, both keep doing so.

## 5. Rules

1. `money.py` is the only module that rounds. Outside it, no module calls
   `round`, `math.floor`, `math.ceil`, `math.trunc`, `quantize`,
   `to_integral`, `to_integral_value` or `to_integral_exact`, and no module
   writes a number with a precision: no format specification such as
   `:.2f` in an f-string, `format()` or `str.format`, and no `%.1f`
   formatting. No module but `money.py` names a decimal rounding constant
   (`ROUND_HALF_UP` and the others) or defines `CENT`.
2. No module reads or changes the decimal context (`getcontext`,
   `setcontext`, `localcontext`, `DefaultContext` and the other context
   objects), `money.py` included. Every `quantize` and `to_integral_*` in
   `money.py` names its rounding.
3. Public functions and classes of the other modules keep their names and
   their parameters. You may add keyword-only parameters with defaults.
4. The command line keeps its exact output for every command, option and
   input: standard output, standard error and exit status, byte for byte.
5. The tests in `tests/` keep passing without changes. Add tests for
   `money` in `tests/test_money.py`.

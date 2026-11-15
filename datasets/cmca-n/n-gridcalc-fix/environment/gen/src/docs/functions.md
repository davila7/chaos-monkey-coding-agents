# Functions

This note covers function calls, how arguments are passed, and each
function. Function names are not case-sensitive: `sum(A1:A3)` is
`SUM(A1:A3)`.

## 1. Calls and arguments

1.1 A call is a name, `(`, arguments separated by commas, and `)`. A call to a
name that is not in this note evaluates to `#NAME?` and its arguments are not
evaluated. A call with fewer or more arguments than the function takes
evaluates to `#VALUE!`.

1.2 **Reference arguments.** An argument written as a single reference or as
a range, alone or inside parentheses, is a reference argument. Its cells are:

- for a single reference, that one cell, whose value is empty when the sheet
  does not define it;
- for a range, the cells the sheet defines inside the rectangle, in cell order
  (`formulas.md` 4.4). Undefined cells of a range are not part of it.

Any other argument, such as `A1+0`, `"4"` or `IF(B1, A1, A2)`, is an
expression argument. It has one value.

1.3 **Errors.** For every function except `COUNT`, `IF` and `IFERROR`, the
expression arguments are evaluated first, in order, and the first one whose
value is an error value is the result of the call. Error values inside
reference arguments are handled by each function, as stated below. `COUNT`
never passes an error on. `IF` and `IFERROR` evaluate only what they use
(section 6).

1.4 A function that reads one value from an argument (`ROUND`, `ABS`, `LEN`,
`NOT`, the condition of `IF`) reads the value of a single reference as it is;
a range there gives `#VALUE!`.

## 2. SUM, AVERAGE, MIN, MAX

2.1 Each argument contributes numbers:

- a reference argument contributes those of its cells that are numbers. Cells
  that hold text, including text that holds a number such as `'42`, booleans
  and empty cells are skipped. If any of its cells is an error value, the
  first one in cell order is the result of the call.
- an expression argument is read as a number (`values.md` 2.1): `TRUE` gives
  1, `"4"` gives 4, and `"x"` gives `#VALUE!`, which is the result of the
  call.

Arguments are taken in order, so an error value in an earlier argument wins.

2.2 `SUM` adds the numbers; with none it is 0. `AVERAGE` divides their sum by
how many there are; with none it is `#DIV/0!`. `MIN` and `MAX` give the
smallest and the largest; with none they are 0.

2.3 Examples, with `A1` = 3, `A2` = `'4`, `A3` = `TRUE`, `A4` = 5 and `A5`
undefined: `SUM(A1:A5)` is 8, `SUM(A2)` is 0, `SUM(A1, "4")` is 7,
`AVERAGE(A1:A5)` is 4 and `AVERAGE(A5, 1)` is 1.

## 3. COUNT

3.1 `COUNT` gives how many numbers its arguments hold. A reference argument
counts its cells that are numbers. An expression argument counts 1 when its
value can be read as a number (`values.md` 2.1) and is neither empty nor an
error value: `COUNT(2, TRUE, "7", "x")` is 3.

3.2 Error values are never counted and never passed on: with `A1` = 1 and
`A2` = `=1/0`, `COUNT(A1:A2)` is 1 and `COUNT(1/0)` is 0.

## 4. ROUND, ABS

4.1 `ROUND(x)` and `ROUND(x, digits)` read both arguments as numbers.
`digits` is 0 when left out and is cut to a whole number toward zero; outside
-10 to 10 it gives `#VALUE!`. `x` is rounded to that many decimal places,
halves away from zero, on the shortest decimal form that reads back as `x`:
`ROUND(2.5)` is 3, `ROUND(-2.5)` is -3, `ROUND(2.675, 2)` is 2.68 and
`ROUND(1234, -2)` is 1200.

4.2 `ABS(x)` reads `x` as a number and gives its absolute value.

## 5. CONCAT, LEN

5.1 `CONCAT` joins its arguments read as text (`values.md` 2.2). A reference
argument contributes all its cells in cell order, an empty single reference
as `""`. The first error value met, in argument and then cell order, is the
result.

5.2 `LEN(x)` gives the number of characters of `x` read as text.

## 6. AND, OR, NOT, IF, IFERROR

6.1 `AND` and `OR` take one or more arguments. A reference argument
contributes its cells that are booleans or numbers, a number being `TRUE`
unless it is 0; text and empty cells are skipped, and an error value among the
cells is the result. An expression argument is read as a boolean
(`values.md` 2.4). With no boolean at all, the result is `#VALUE!`. `AND` is
`TRUE` when every value is `TRUE`, `OR` when one is.

6.2 `NOT(x)` reads `x` as a boolean and gives the other one.

6.3 `IF(condition, then)` and `IF(condition, then, else)` read the condition
as a boolean. An error value there is the result. Otherwise only the branch
taken is evaluated, and its value is the result as it is; without an else
branch a false condition gives `FALSE`. So `IF(B1=0, 0, A1/B1)` is 0 when
`B1` is 0, and `IF(TRUE, A9)` is empty when `A9` is undefined.

6.4 `IFERROR(x, alternative)` evaluates `x`. When `x` is an error value, the
result is the alternative, which is evaluated only then; otherwise it is `x`.

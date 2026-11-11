# Values

This note covers the kinds of values, how one kind is read as another, how
values compare, the error values and how they spread, and cycles.

## 1. Kinds

1.1 A value is a number, a text, a boolean, empty, or an error value.

1.2 Numbers are double-precision floating point numbers. There is one kind of
number; `2` and `2.0` are the same value.

1.3 A boolean is `TRUE` or `FALSE`. A boolean is not a number, even though
it can be read as one (section 2).

1.4 Empty is the value of a cell the sheet does not define. It is neither 0
nor the text `""`; how it reads depends on where it is used (2.5, 4.2,
`functions.md`).

## 2. Reading one kind as another

2.1 **As a number** (operands of `+ - * / ^`, prefix `-` and `+`, `%`, and
the arguments `functions.md` says are read as numbers): a number is itself;
`TRUE` is 1 and `FALSE` is 0; empty is 0; a text that holds a number
(2.3) is that number; any other text gives `#VALUE!`.

2.2 **As text** (operands of `&`, and the arguments `functions.md` says are
read as text): a text is itself; a number is written as in section 3;
`TRUE` and `FALSE` are the texts `TRUE` and `FALSE`; empty is the text `""`.

2.3 A text holds a number when, after leading and trailing spaces and tabs
are removed, it is an optional sign followed by a number written as in
`formulas.md` 2.1: `"42"`, `" -1.5 "`, `"1e3"` and `".5"` hold numbers;
`"1,000"`, `"5%"`, `"0x1F"` and `""` do not.

2.4 **As a boolean** (the condition of `IF`, the arguments of `AND`, `OR`
and `NOT`): a boolean is itself; a number is `TRUE` unless it is 0; empty is
`FALSE`; the texts `TRUE` and `FALSE`, in any case, are those booleans; any
other text gives `#VALUE!`.

2.5 **Empty.** An undefined cell read by an operator is converted by 2.1,
2.2 or 2.4 like any other value: `A9+1` is 1 and `A9&"x"` is `x` when `A9` is
undefined. Functions treat empty cells on their own terms (`functions.md`
1.2). A formula whose result is empty, such as `=A9`, has the value 0.

## 3. Numbers as text

3.1 A number becomes text when `&`, `CONCAT` or `LEN` read it as text.

3.2 The text of a number is its `%.10g` form, as C's `printf` writes it: at
most 10 significant digits, without trailing zeros and without a trailing
decimal point. The exponent form is used when the decimal exponent is below
-4 or at least 10, with a sign and at least two digits. Negative zero is
written `0`.

| Number | Text |
|---|---|
| 2 | `2` |
| 0.5 | `0.5` |
| 1/3 | `0.3333333333` |
| 0.1+0.2 | `0.3` |
| 1234567.125 | `1234567.125` |
| 12345678901 | `1.23456789e+10` |
| 0.000012 | `1.2e-05` |

## 4. Comparisons

4.1 The comparison operators give `TRUE` or `FALSE`. An operand that is an
error value gives that error instead (section 5).

4.2 When one operand is empty, it is read as the blank of the other one's
kind: 0 next to a number, `""` next to a text, `FALSE` next to a boolean.
Two empty operands are equal. So with `A9` undefined, `A9=0`, `A9=""` and
`A9=FALSE` are all `TRUE`.

4.3 Values of the same kind compare naturally: numbers by size, booleans with
`FALSE` before `TRUE`, and texts by code point order after both are put in
lower case, so `"apple"="APPLE"` is `TRUE` and `"a"<"B"` is `TRUE`.

4.4 Values of different kinds are never equal and order as numbers before
texts before booleans: `1<"a"`, `"z"<TRUE` and `99<FALSE` are all `TRUE`, and
`1="1"` is `FALSE`. A text is not read as a number for a comparison.

## 5. Error values

5.1 The error values are:

| Error | Cause |
|---|---|
| `#DIV/0!` | division by zero; `0^` a negative power; `AVERAGE` of no numbers |
| `#VALUE!` | a value of the wrong kind (2.1, 2.4); a range outside a function; a function given the wrong number of arguments |
| `#REF!` | a reference or range outside the grid (`formulas.md` 4.1) |
| `#NAME?` | an unknown name or function |
| `#NUM!` | a result that is not a finite number; a negative number to a power that is not a whole number |
| `#CYCLE!` | a cell in a cycle (section 6), or one that reads such a cell |
| `#PARSE!` | a formula that cannot be read (`formulas.md` 2.6) |

5.2 **Spreading.** An operator whose operand is an error value gives that
error. When both operands are errors, the left one wins: `(1/0)+FOO` is
`#DIV/0!`. Both operands of an operator are always evaluated.

5.3 Functions pass errors on as `functions.md` 1.3 says. `IF` and `IFERROR`
only evaluate the arguments they use, so an error in a branch that is not
taken never reaches the result.

5.4 An error value is a value like any other: a cell that holds one is typed
`error` in the document (`output.md` 2.3), and other cells may read it.

## 6. Cycles

6.1 A formula names the cells of the sheet that its references point to and
the defined cells inside its ranges, whether or not evaluating it reads them.
A cell is in a cycle when it can reach itself by following those names. A
cell that names itself is a cycle on its own.

6.2 Every cell in a cycle has the value `#CYCLE!`, without being evaluated.
This holds even when the reference that closes the cycle sits in a branch of
`IF` that is not taken: `A1: =IF(TRUE, 1, A1)` is `#CYCLE!`.

6.3 A cell outside a cycle is evaluated as usual. If it reads a cell in a
cycle, it gets `#CYCLE!` by 5.2 or 5.3.

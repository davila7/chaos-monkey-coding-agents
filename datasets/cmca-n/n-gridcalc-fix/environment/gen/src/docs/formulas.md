# Formulas

This note covers how the text of a formula after its leading `=` is read:
tokens, operators and their precedence, references and ranges, and the cell
order that documents, ranges and refs listings use.

## 1. Overview

1.1 A formula is an expression. It is built from literals (numbers, strings,
`TRUE`, `FALSE`), references to cells, ranges, function calls, operators and
parentheses.

1.2 Spaces and tabs between tokens are ignored. They are never needed, except
inside strings, where they are kept.

## 2. Tokens

2.1 **Numbers.** A number token is digits with an optional fraction and an
optional exponent:

    digits [ "." [digits] ]  or  "." digits,  then optionally  ("e" | "E") ["+" | "-"] digits

So `12`, `12.`, `.5`, `1.25`, `1.5e3`, `2E-2` and `7e+1` are single number
tokens. A sign in front of a number is not part of the token; it is a prefix
operator (section 3).

2.2 **Strings.** A string is written between double quotes. Inside it, two
double quotes stand for one: `"say ""hi"""` is the text `say "hi"`. A string
with no closing quote cannot be read.

2.3 **References.** A reference is a column name followed by a row number,
each optionally preceded by `$`: `A1`, `$A1`, `A$1`, `$A$1`, `ab12`. The `$`
signs do not change which cell is meant. A reference must not be followed
directly by a letter, a digit, `_` or `(`.

2.4 **Names.** A name is a letter or `_` followed by letters, digits and `_`.
A name followed by `(` is a function call (`functions.md`). Names are not
case-sensitive. `TRUE` and `FALSE` not followed by `(` are the boolean
literals. Any other name is an unknown name and evaluates to `#NAME?`.

2.5 **Operators and punctuation.** `+ - * / ^ & % = <> < > <= >= ( ) , :`.
`<>`, `<=` and `>=` are single tokens.

2.6 A formula that cannot be split into tokens, or whose tokens do not form
one expression by section 3, cannot be read. Its cell takes the value
`#PARSE!` and its refs listing is empty (`output.md` 2.5). An empty formula
(`=` alone) cannot be read either.

## 3. Operators and precedence

3.1 Operators bind in this order, from loosest to tightest:

| Level | Operators | Kind | Grouping |
|---|---|---|---|
| 1 | `=` `<>` `<` `>` `<=` `>=` | comparison | left |
| 2 | `&` | text concatenation | left |
| 3 | `+` `-` | addition, subtraction | left |
| 4 | `*` `/` | multiplication, division | left |
| 5 | `-` `+` | prefix minus and plus | |
| 6 | `^` | power | right |
| 7 | `%` | postfix percent | |
| 8 | `:` | range | |

3.2 A tighter operator takes its operands first. So `1+2*3` is 7,
`"a"&1+2` is `a3` and `1+2=3` is `TRUE`.

3.3 Grouping to the left means `10-4-3` is `(10-4)-3`, which is 3, and
`12/3/2` is 2. `^` groups to the right: `2^3^2` is `2^(3^2)`, which is 512.

3.4 The prefix minus is looser than `^`. `-2^2` is `-(2^2)`, which is -4, and
`-A1^2` is minus the square of `A1`. To square a negative number, write
`(-2)^2`. The operand of `^` on its right may itself start with a prefix
operator: `2^-1` is `2^(-1)`, which is 0.5.

3.5 `%` divides the value before it by 100: `50%` is 0.5, `-50%` is -0.5 and
`2*3%` is 0.06.

3.6 Parentheses group as usual and may hold any expression, including a range
given to a function: `SUM((A1:A3))` is `SUM(A1:A3)`.

## 4. References, ranges and cell order

4.1 **Grid.** Columns are named `A` to `Z`, then `AA` to `AZ`, `BA` and so on
up to `ZZ`, so `A` is column 1, `Z` is 26, `AA` is 27, `AZ` is 52 and `ZZ` is
702. Rows are numbered 1 to 9999. A reference to a column after `ZZ` or a row
outside 1 to 9999 (such as `AAA1` or `A0`) can be read, but evaluates to
`#REF!` and is left out of the refs listing.

4.2 **Ranges.** `X:Y`, where `X` and `Y` are references, names the rectangle
of cells with `X` and `Y` as opposite corners. The two corners may be given in
any order: `A1:B3`, `B3:A1`, `A3:B1` and `B1:A3` all name the same six cells.
A range is written in its normal form `TOPLEFT:BOTTOMRIGHT` wherever the
package writes it (`output.md` 2.5). A range with a corner outside the grid
evaluates to `#REF!`.

4.3 A range only stands as a function argument (`functions.md` 1.2). Used
anywhere else, as in `A1:B2+1`, it evaluates to `#VALUE!`.

4.4 **Cell order.** Cells are put in cell order by column first and then by
row, both as numbers: `A1, A2, ..., A10, B1, ..., Z1, AA1`. Documents
(`output.md` 2.2), the cells of a range (`functions.md` 1.2) and refs
listings (`output.md` 2.5) all use cell order.

# Changelog

## 2.6.1

- `tariffs` lists the VAT rate with one decimal.

## 2.6.0

- Quotes in JSON.

## 2.5.0

- Credits imported from the old customer system. They arrive as JSON
  numbers and are settled with the old system's arithmetic so that customer
  balances agree with its statements.

## 2.4.0

- Cash rules per currency: `whole` for currencies paid in whole units,
  a step such as `0.05` for coins.

## 2.3.0

- `batch` computes bills on a thread pool (`--workers`, default 4).

## 2.0.0

- Standing charge segments: a rate change inside a period.

## 1.4.0

- VAT rounds half to even, as the tax office requires.

## 1.0.0

- First release. Amounts round half up.

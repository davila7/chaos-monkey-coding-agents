# Changelog

## 2.6.0

- `audit` for the security review: rights people hold themselves, without
  delegations, so cover arrangements do not show up as standing access.

## 2.5.0

- Delegations (`delegations.csv`) for cover during leave. `list` and
  `show` let the delegate see what the lender sees. `edit` lets the
  delegate change what the lender owns or was granted, but not with the
  lender's role. `share` and `delete` do not honor delegations.

## 2.4.0

- Grants on every document (`*`). Readers trust them only when an admin
  granted them; `edit` was not changed.

## 2.3.0

- `edit` keeps grants open through their `until` minute: people were
  locked out of documents in the last minute of their grant while saving.
- Suspensions end on a day: `edit` lets the account work again from the
  start of `suspended_until`, readers from the day after.

## 2.2.0

- `show` lists documents of an empty team to users without a team (the
  shared drive import).

## 2.1.0

- `share` and `delete` refuse any suspended account, whatever its day.
- Role names are matched in any case in `list` and `show`.

## 2.0.0

- Workspace files as CSV; `--at` replaces the machine clock.

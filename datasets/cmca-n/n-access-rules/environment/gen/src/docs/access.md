# Access rules in one place

Status: agreed, ready to implement. Owner: shelf team.

## 1. Why

Every command of `docshelf` decides on its own who may do what: `listing`,
`show`, `edit`, `share`, `delete` and `audit` each carry their own copy of
the checks for roles, ownership, team documents, grants, delegations and
suspended accounts. The copies were made one from another over the years
and drifted. The next command (comments) needs one place where the rules
live and can be read.

This is a refactor. No command may change what it prints, what it writes
to the workspace or its exit status, for any workspace, and that includes
the places where the copies disagree with each other. If something looks
like a bug, keep it as it is and say so in your summary; fixing it is a
separate change.

## 2. The module

Create `docshelf/access.py` with exactly these public names:

```python
ROLE_EXACT = "exact"
ROLE_LOWER = "lower"
ROLE_FOLDED = "folded"
SUSPEND_THROUGH = "through"
SUSPEND_BEFORE = "before"
SUSPEND_STATUS = "status"
END_INCLUSIVE = "inclusive"
END_EXCLUSIVE = "exclusive"
DELEGATE_ALL = "all"
DELEGATE_OWNED = "owned"
DELEGATE_NONE = "none"

@dataclass(frozen=True)
class Rules:
    roles: str
    suspension: str
    ends: str
    delegation: str
    blank_team: bool
    wildcard_admin: bool

def role(user: User, rules: Rules) -> str: ...
def suspended(user: User, at: datetime, rules: Rules) -> bool: ...
def is_admin(user: User, at: datetime, rules: Rules) -> bool: ...
def acting_for(store: Store, user: User, at: datetime, rules: Rules) -> list[User]: ...
def can_read(store: Store, user_id: str, doc: Doc, at: datetime, rules: Rules) -> bool: ...
def can_write(store: Store, user_id: str, doc: Doc, at: datetime, rules: Rules) -> bool: ...
def can_share(store: Store, user_id: str, doc: Doc, right: str, at: datetime, rules: Rules) -> bool: ...
def can_delete(store: Store, user_id: str, doc: Doc, at: datetime, rules: Rules) -> bool: ...
```

`User`, `Doc` and `Store` are the classes of `docshelf/store.py`. Helpers
start with `_`. `access.py` may import from `docshelf.store` and from the
standard library, and from nothing else in `docshelf`.

`Rules(...)` takes its fields by name or in the order above and raises
`ValueError` when a field holds a value not listed for it: `roles` is one of
the three `ROLE_` values, `suspension` one of the `SUSPEND_` values, `ends`
one of the `END_` values, `delegation` one of the `DELEGATE_` values, and
`blank_team` and `wildcard_admin` are `True` or `False` (not `0`, `1` or
other values). Two `Rules` with the same fields are equal.

### 2.1 What each field means

- `roles`: how a role name is read before it is compared with `admin` or
  `editor`. `ROLE_EXACT` as written in `users.csv`, `ROLE_LOWER` after
  `lower()`, `ROLE_FOLDED` after `strip()` and `lower()`. `role()` returns
  the name read that way.
- `suspension`: when an account whose `status` is `suspended` counts as
  suspended at time `at`. `SUSPEND_THROUGH`: up to and including its
  `suspended_until` day. `SUSPEND_BEFORE`: before its `suspended_until`
  day. `SUSPEND_STATUS`: always, whatever the day. An empty
  `suspended_until` means always for all three. An `active` account is
  never suspended. `suspended()` answers this.
- `ends`: when a grant or a delegation stops. Both are open from their
  `from` minute (an empty `from` means always) to their `until` minute (an
  empty `until` means never). With `END_INCLUSIVE` they are still open at
  the `until` minute, with `END_EXCLUSIVE` they are not.
- `delegation`: what a delegation lends. A row of `delegations.csv` open at
  `at` lets `to_user` act for `from_user`. `DELEGATE_ALL`: the delegate
  holds everything the lender holds (role, team, ownership, grants).
  `DELEGATE_OWNED`: only what the lender owns or was granted.
  `DELEGATE_NONE`: delegations are ignored.
- `blank_team`: whether a user with an empty team counts as a member of a
  `team` document whose team is empty too.
- `wildcard_admin`: whether a grant on every document (`doc` is `*`) holds
  only when its `granted_by` user is an admin (role read with `roles`;
  suspension and `ends` do not apply to the granter). When `False`, every
  `*` grant holds whoever granted it.

### 2.2 The functions

- `is_admin(user, at, rules)`: `role()` is `admin` and the user is not
  `suspended()`.
- `acting_for(store, user, at, rules)`: `user` first, then each lender in
  the order of `delegations.csv`: the `from_user` of every delegation to
  `user` that is open at `at` (by `ends`), when that user exists, is not
  `user`, is not `suspended()` and is not listed yet. One step only: a
  lender's own lenders are not followed. With `DELEGATE_NONE` the list is
  `[user]`.
- `can_read`, `can_write`, `can_share`, `can_delete`: `False` when
  `user_id` is not a user or the user is `suspended()`. Otherwise `True`
  when any person in `acting_for()` gives the right as below. A person
  "carries the role" when it is the user, or when `delegation` is
  `DELEGATE_ALL`; role and team count only for people who carry the role.
  A grant "applies" to the document when its `user` is that person, it is
  open at `at` (by `ends`), and its `doc` is the document's id or `*` (see
  `wildcard_admin`).
  - read: the document is `public`; or the person is an admin by role; or
    owns the document; or the document is `team` and the person is in its
    team (see `blank_team`); or a grant of any right applies.
  - write: admin by role; owner; an `editor` by role in the team of a
    `team` document; or a `write` grant applies.
  - share `right`: admin by role; owner; or `right` is `read` and a
    `write` grant applies whose `doc` is the document's id itself (a `*`
    grant never counts here).
  - delete: admin by role; owner.

## 3. Where the checks are today

We found these by searching for `role`, `status` and `grants`:

| Site | Today |
|---|---|
| `listing._can_see`, `listing.visible_docs` | folded roles, suspended through the until day, grants and delegations end at their until minute, lenders hold everything |
| `show._rights` | like `listing`, for reading and for the `you can` line |
| `edit._may_edit`, `edit.edit` | lower-case roles; suspension ends when its until day starts; grants and delegations stay open through their until minute; a delegate edits with what the lender owns or was granted |
| `share._may_share`, `share.share` | roles as written; the status alone; delegates may not share |
| `delete.delete` | roles as written; the status alone |
| `audit.rows` and its helpers | like `listing`, without delegations |

The table is a summary. The code is what the commands do, and where the
two differ, the code wins.

## 4. Rules

1. `access.py` is the only module that decides access. Outside it no
   module reads a user's `role`, `status` or `suspended_until`, the
   store's `grants` or `delegations`, or a grant's `granted_by`, neither
   directly nor through `getattr`, `vars` or `__dict__`; none
   compares anything with a document's `owner`, `team` or `level`; and
   none holds the role names `admin` or `editor` as strings of their own.
2. Each command module (`listing`, `show`, `edit`, `share`, `delete`,
   `audit`) defines a module-level `RULES = access.Rules(...)` with what
   that command does today and passes it to every call into `access`.
3. `store.py`, `render.py` and `errors.py` are not part of this change:
   leave them byte for byte as they are.
4. Public functions and classes of the other modules keep their names and
   their parameters. You may add keyword-only parameters with defaults.
5. The command line keeps its exact behavior for every command, option and
   workspace: standard output, standard error, exit status and every file
   in the workspace afterwards (including `activity.log`), byte for byte.
6. The tests in `tests/` keep passing without changes. Add tests for
   `access` in `tests/test_access.py`.

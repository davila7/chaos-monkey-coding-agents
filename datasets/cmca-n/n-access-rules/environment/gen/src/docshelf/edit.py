"""The edit command: change the title of a document."""

from datetime import datetime
from pathlib import Path

from docshelf import store as files
from docshelf.errors import DataError, Denied
from docshelf.store import Doc, Store, User


def _role(user: User) -> str:
    return user.role.lower()


def _suspended(user: User, at: datetime) -> bool:
    # The until day is the first day the account may edit again.
    return user.status == "suspended" and (user.suspended_until is None or at.date() < user.suspended_until)


def _active(item, at: datetime) -> bool:
    if item.start is not None and at < item.start:
        return False
    return item.end is None or at <= item.end


def _may_edit(store: Store, user: User, doc: Doc, at: datetime) -> bool:
    if _role(user) == "admin":
        return True
    if _role(user) == "editor" and doc.level == "team" and user.team and user.team == doc.team:
        return True
    # A delegate edits with what the lender owns or was granted, not with the lender's role or team.
    people = [user]
    for d in store.delegations:
        if d.target == user.id and _active(d, at):
            lender = store.users.get(d.source)
            if lender is not None and lender not in people and not _suspended(lender, at):
                people.append(lender)
    names = {p.id for p in people}
    if doc.owner in names:
        return True
    return any(g.right == "write" and g.user in names and g.doc in (doc.id, "*") and _active(g, at) for g in store.grants)


def edit(store: Store, folder: Path, user_id: str, doc_id: str, title: str, at: datetime) -> str:
    doc = store.docs.get(doc_id)
    if doc is None:
        raise DataError(f"no such document: {doc_id}")
    if title.strip() == "" or "\n" in title:
        raise DataError("a title is one non-empty line")
    user = store.users[user_id]
    if _suspended(user, at):
        files.log(folder, at, user_id, "edit", doc_id, "suspended")
        raise Denied(f"account suspended: {user_id}")
    if not _may_edit(store, user, doc, at):
        files.log(folder, at, user_id, "edit", doc_id, "denied")
        raise Denied(f"permission denied: {doc_id}")
    files.set_title(folder, doc_id, title)
    files.log(folder, at, user_id, "edit", doc_id, "ok")
    return f"updated {doc_id}: {doc.title!r} -> {title!r}\n"

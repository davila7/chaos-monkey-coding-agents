"""The show command: one document and what the user may do with it."""

from datetime import datetime

from docshelf.errors import DataError, Denied
from docshelf.store import Doc, Store, User, format_time


def _is_admin(user: User) -> bool:
    return user.role.strip().lower() == "admin"


def _is_editor(user: User) -> bool:
    return user.role.strip().lower() == "editor"


def _blocked(user: User, at: datetime) -> bool:
    return user.status == "suspended" and (user.suspended_until is None or at.date() <= user.suspended_until)


def _live(start, end, at: datetime) -> bool:
    if start is not None and at < start:
        return False
    if end is not None and at >= end:
        return False
    return True


def _acting_as(store: Store, user: User, at: datetime) -> list:
    people = [user]
    for d in store.delegations:
        if d.target == user.id and _live(d.start, d.end, at):
            lender = store.users.get(d.source)
            if lender is not None and lender not in people and not _blocked(lender, at):
                people.append(lender)
    return people


def _grant_applies(store: Store, g, doc: Doc) -> bool:
    if g.doc == doc.id:
        return True
    if g.doc != "*":
        return False
    by = store.users.get(g.granted_by)
    return by is not None and _is_admin(by)


def _rights(store: Store, user: User, doc: Doc, at: datetime) -> set:
    """read and write as the document page shows them."""
    if _blocked(user, at):
        return set()
    out = {"read"} if doc.level == "public" else set()
    for who in _acting_as(store, user, at):
        if _is_admin(who) or who.id == doc.owner:
            return {"read", "write"}
        if doc.level == "team" and who.team == doc.team:
            out.add("read")
            if _is_editor(who):
                out.add("write")
        for g in store.grants:
            if g.user == who.id and _live(g.start, g.end, at) and _grant_applies(store, g, doc):
                out.add("read")
                if g.right == "write":
                    out.add("write")
    return out


def describe(store: Store, user_id: str, doc_id: str, at: datetime) -> list:
    doc = store.docs.get(doc_id)
    if doc is None:
        raise DataError(f"no such document: {doc_id}")
    rights = _rights(store, store.users[user_id], doc, at)
    if "read" not in rights:
        raise Denied(f"access denied: {doc_id}", status=3)
    return [
        ("doc", doc.id),
        ("title", doc.title),
        ("owner", doc.owner),
        ("team", doc.team or "-"),
        ("level", doc.level),
        ("you can", "read, edit" if "write" in rights else "read"),
        ("as of", format_time(at)),
    ]

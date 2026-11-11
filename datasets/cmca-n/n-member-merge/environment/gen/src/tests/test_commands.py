"""The commands of release 3.1 (docs/commands.md)."""

import unittest

from tests.support import Workspace, member


class ShowListFindTest(unittest.TestCase):
    def test_show_through_alias(self):
        ws = Workspace(self, members=[member(19, "Grace Lee", joined="21/03/2014", tags="import-2019;swim")],
                       aliases={"M-5": "M-0019"})
        self.assertEqual(ws.run("show", "m-5"), (0, "M-0005 -> M-0019\nid: M-0019\nname: Grace Lee\nemail: \nphone: \n"
                                                  "dob: \njoined: 21/03/2014\nexpires: \nmarketing: \n"
                                                  "tags: import-2019, swim\nupdated: 2024-01-01T00:00:00Z\n", ""))

    def test_list_by_tag(self):
        ws = Workspace(self, members=[member(2, "Ben Ali", tags=["row"], expires="2026-03-31"),
                                      member(10, "Isla Doyle", tags="import-2019;row"), member(4, "Uma Sato")])
        self.assertEqual(ws.run("list", "--tag", "row")[1],
                         "M-0002  2026-03-31  Ben Ali\nM-0010  -           Isla Doyle\n")

    def test_find_by_phone_digits(self):
        ws = Workspace(self, members=[member(2, "Ben Ali", phone="07700 900123"), member(3, "Uma Sato", phone="+44 7700 900999")])
        self.assertEqual(ws.run("find", "7700-900")[1], "M-0002  -           Ben Ali\nM-0003  -           Uma Sato\n")
        self.assertEqual(ws.run("find", "uma")[1], "M-0003  -           Uma Sato\n")

    def test_ids(self):
        ws = Workspace(self, members=[member(2, "Ben Ali")])
        self.assertEqual(ws.run("show", "X-2")[::2], (2, "bad-id"))
        self.assertEqual(ws.run("show", "M-9")[::2], (3, "unknown-member"))


class ChangeTest(unittest.TestCase):
    def test_edit_appends_audit_line(self):
        ws = Workspace(self, members=[member(7, "Ben Ali", email="ben@outlook.com")],
                       audit=[{"seq": 41, "op": "pay"}, {"seq": 44, "op": "renew"}])
        self.assertEqual(ws.run("edit", "M-7", "email", "ben.ali@outlook.com", by="desk"),
                         (0, "M-0007 email: ben@outlook.com -> ben.ali@outlook.com\n", ""))
        self.assertEqual(ws.text("audit.jsonl").splitlines()[-1],
                         '{"seq":45,"at":"2026-11-02T09:15:00Z","op":"edit","by":"desk","member":"M-0007","changes":'
                         '{"email":["ben@outlook.com","ben.ali@outlook.com"],"updated":["2024-01-01T00:00:00Z","2026-11-02T09:15:00Z"]}}')
        self.assertEqual(ws.members()[0]["updated"], "2026-11-02T09:15:00Z")

    def test_edit_unchanged_writes_nothing(self):
        ws = Workspace(self, members=[member(7, "Ben Ali", marketing="no")])
        before = ws.snapshot()
        self.assertEqual(ws.run("edit", "M-0007", "marketing", "no"), (0, "M-0007 marketing unchanged\n", ""))
        self.assertEqual(ws.snapshot(), before)

    def test_renew(self):
        ws = Workspace(self, members=[member(7, "Ben Ali", expires="2026-03-31")])
        self.assertEqual(ws.run("renew", "M-7", "2026-03-31")[::2], (3, "not-later"))
        self.assertEqual(ws.run("renew", "M-7", "2027-03-31", now="2026-11-02T10:15:00+01:00"),
                         (0, "M-0007 expires 2027-03-31\n", ""))
        self.assertEqual(ws.members()[0]["updated"], "2026-11-02T09:15:00Z")

    def test_pay_through_alias(self):
        ws = Workspace(self, members=[member(19, "Grace Lee")], aliases={"M-0005": "M-0019"},
                       payments=["P-00001,M-5,2025-01-05,45.00"])
        self.assertEqual(ws.run("pay", "M-5", "12.50"), (0, "P-00002 M-0019 12.50\n", ""))
        self.assertEqual(ws.text("payments.csv"),
                         "payment,member,day,amount\nP-00001,M-5,2025-01-05,45.00\nP-00002,M-0019,2026-11-02,12.50\n")
        self.assertEqual(ws.run("pay", "M-19", "12")[::2], (2, "bad-amount"))

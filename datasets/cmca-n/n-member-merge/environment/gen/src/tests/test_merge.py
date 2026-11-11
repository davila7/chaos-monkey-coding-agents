"""Release 3.2: merge (docs/merge.md)."""

import json
import unittest

from tests.support import Workspace, member

ANNA = [member(3, "Anna Kowalska", email="anna.k@outlook.com", joined="2016-04-02", tags=["swim"],
               updated="2025-02-01T10:00:00Z"),
        member(42, "ANNA KOWALSKA", email="Anna.K+club@Outlook.com", phone="07700 900123", joined="2021-09-01",
               expires="2026-08-31", marketing="yes", updated="2025-06-01T08:00:00+01:00")]
ANNA_PLAN = ('merge M-0003 <- M-0042 (email)\n'
             '  email: "anna.k@outlook.com" -> "Anna.K+club@Outlook.com"\n'
             '  phone: "" -> "07700 900123"\n'
             '  expires: "" -> "2026-08-31"\n'
             '  marketing: "" -> "yes"\n'
             '  updated: "2025-02-01T10:00:00Z" -> "2026-11-02T09:15:00Z"\n'
             '1 groups, 1 members merged, 0 pairs kept apart\n')


class MergeTest(unittest.TestCase):
    def test_dry_run(self):
        ws = Workspace(self, members=ANNA)
        before = ws.snapshot()
        self.assertEqual(ws.run("merge"), (0, ANNA_PLAN + "dry run: nothing written\n", ""))
        self.assertEqual(ws.snapshot(), before)

    def test_apply(self):
        ws = Workspace(self, members=ANNA, aliases={"M-7": "M-0042"}, audit=[{"seq": 900, "op": "pay"}],
                       payments=["P-00001,M-42,2025-01-05,45.00", "P-00002,m-0003,2025-02-05,45.00",
                                 "P-00003,M-7,2025-03-05,25.00"])
        self.assertEqual(ws.run("merge", "--apply", by="desk"), (0, ANNA_PLAN, ""))
        self.assertEqual(json.loads(ws.text("aliases.json")), {"M-0007": "M-0003", "M-0042": "M-0003"})
        self.assertEqual(ws.text("payments.csv"), "payment,member,day,amount\nP-00001,M-0003,2025-01-05,45.00\n"
                                                  "P-00002,m-0003,2025-02-05,45.00\nP-00003,M-0003,2025-03-05,25.00\n")
        self.assertEqual(ws.text("audit.jsonl").splitlines()[-1],
                         '{"seq":901,"at":"2026-11-02T09:15:00Z","op":"merge","by":"desk","member":"M-0003",'
                         '"merged":["M-0042"],"rules":["email"],"changes":{"email":["anna.k@outlook.com",'
                         '"Anna.K+club@Outlook.com"],"phone":["","07700 900123"],"expires":["","2026-08-31"],'
                         '"marketing":["","yes"],"updated":["2025-02-01T10:00:00Z","2026-11-02T09:15:00Z"]},'
                         '"from":{"email":"M-0042","phone":"M-0042","expires":"M-0042"}}')
        self.assertEqual([m["id"] for m in ws.members()], ["M-0003"])
        self.assertEqual(ws.run("show", "M-42")[1].splitlines()[:2], ["M-0042 -> M-0003", "id: M-0003"])

    def test_kept_apart_by_birth_day(self):
        ws = Workspace(self, members=[
            member(12, "Liam Byrne", email="byrnes@gmail.com", dob="1970-03-01", joined="2015-01-10"),
            member(40, "Liam Byrne", email="byrnes@gmail.com", dob="2001-07-19", joined="2018-05-05"),
            member(77, "Liam Byrne", email="by.rnes@gmail.com", joined="2022-02-02")])
        self.assertEqual(ws.run("merge")[1], 'merge M-0012 <- M-0077 (email)\n'
                                             '  updated: "2024-01-01T00:00:00Z" -> "2026-11-02T09:15:00Z"\n'
                                             'kept apart M-0012 M-0040 (email)\n'
                                             'kept apart M-0040 M-0077 (email)\n'
                                             '1 groups, 1 members merged, 2 pairs kept apart\n'
                                             'dry run: nothing written\n')

    def test_import_record_survives(self):
        ws = Workspace(self, members=[
            member(5, "Zoë Novak", dob="1990-05-04", joined="2019-02-01", marketing="yes", updated="2026-01-01T00:00:00Z"),
            member(31, "Zoe Novak", dob="04/05/1990", joined="12/06/2011", marketing="no", tags="import-2019;row",
                   updated="2019-04-01")])
        self.assertEqual(ws.run("merge")[1], 'merge M-0031 <- M-0005 (name-dob)\n'
                                             '  dob: "04/05/1990" -> "1990-05-04"\n'
                                             '  tags: "import-2019;row" -> ["import-2019", "row"]\n'
                                             '  updated: "2019-04-01" -> "2026-11-02T09:15:00Z"\n'
                                             '1 groups, 1 members merged, 0 pairs kept apart\n'
                                             'dry run: nothing written\n')

    def test_nothing_to_merge(self):
        ws = Workspace(self, members=[member(1, "Ben Ali", email="ben@outlook.com"), member(2, "Ben Ali", email="b.ali@outlook.com")])
        before = ws.snapshot()
        self.assertEqual(ws.run("merge", "--apply"), (0, "0 groups, 0 members merged, 0 pairs kept apart\n", ""))
        self.assertEqual(ws.snapshot(), before)

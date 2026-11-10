import json
import unittest

from tests.support import Workspace


class ReceiveTest(unittest.TestCase):
    def test_units_and_journal_line(self):
        ws = Workspace(self, journal=[{"seq": 4, "op": "receive", "sku": "TB-2201", "bin": "a-01", "qty": 3}])
        self.assertEqual(ws.run("receive", "BX-1042", " a-02", "5", by="dock-1"),
                         (0, "#5 receive BX-1042\n  A-02 0 -> 5\n", ""))
        self.assertEqual(ws.journal_lines()[-1],
                         '{"v":2,"seq":5,"op":"receive","by":"dock-1","sku":"BX-1042","effects":[{"bin":"A-02","before":0,"after":5}]}')
        self.assertEqual(ws.state(), {"BX-1042": {"A-02": 5}})

    def test_packs(self):
        ws = Workspace(self, stock={"RL-3300": {"C-01": 2}})
        self.assertEqual(ws.run("receive", "RL-3300", "C-01", "3", "--packs")[1], "#1 receive RL-3300\n  C-01 2 -> 20\n")

    def test_refusals(self):
        ws = Workspace(self)
        self.assertEqual(ws.run("receive", "BX-1042", "B-02", "1")[::2], (3, "retired-bin"))
        self.assertEqual(ws.run("receive", "BX-1042", "Z-09", "1")[::2], (3, "unknown-bin"))
        self.assertEqual(ws.run("receive", "bx-1042", "A-01", "1")[::2], (3, "unknown-sku"))
        self.assertEqual(ws.run("receive", "BX-1042", "A-01", "0")[::2], (2, "usage"))
        self.assertEqual(ws.journal_lines(), [])


class IssueTest(unittest.TestCase):
    def test_pick_order_skips_retired(self):
        ws = Workspace(self, stock={"BX-1042": {"B-01": 2, "A-02": 3, "A-01": 10, "B-02": 50}})
        self.assertEqual(ws.run("issue", "BX-1042", "7")[1], "#1 issue BX-1042\n  B-01 2 -> 0\n  A-02 3 -> 0\n  A-01 10 -> 8\n")
        self.assertEqual(ws.state(), {"BX-1042": {"A-01": 8, "B-02": 50}})

    def test_short(self):
        ws = Workspace(self, stock={"BX-1042": {"A-01": 4, "B-02": 50}})
        self.assertEqual(ws.run("issue", "BX-1042", "5")[::2], (3, "short"))
        self.assertEqual(ws.state(), {"BX-1042": {"A-01": 4, "B-02": 50}})


class MoveTest(unittest.TestCase):
    def test_out_of_retired_bin(self):
        ws = Workspace(self, stock={"TB-2201": {"B-02": 9}})
        self.assertEqual(ws.run("move", "TB-2201", "b-02", "C-01", "9")[1], "#1 move TB-2201\n  B-02 9 -> 0\n  C-01 0 -> 9\n")
        self.assertEqual(ws.state(), {"TB-2201": {"C-01": 9}})

    def test_refusals(self):
        ws = Workspace(self, stock={"TB-2201": {"A-01": 9}})
        self.assertEqual(ws.run("move", "TB-2201", "A-01", "B-02", "1")[::2], (3, "retired-bin"))
        self.assertEqual(ws.run("move", "TB-2201", "A-01", "a-01", "1")[::2], (2, "same-bin"))
        self.assertEqual(ws.run("move", "TB-2201", "A-01", "C-01", "10")[::2], (3, "short"))


class CountFixTest(unittest.TestCase):
    def test_count_records_equal_quantities(self):
        ws = Workspace(self, stock={"TB-2201": {"A-01": 9}})
        self.assertEqual(ws.run("count", "TB-2201", "A-01", "9")[1], "#1 count TB-2201\n  A-01 9 -> 9\n")
        self.assertEqual(ws.run("count", "TB-2201", "B-02", "0")[::2], (3, "retired-bin"))

    def test_fix(self):
        ws = Workspace(self, stock={"TB-2201": {"B-02": 9}})
        self.assertEqual(ws.run("fix", "TB-2201", "B-02", "10")[::2], (3, "retired-bin"))
        self.assertEqual(ws.run("fix", "TB-2201", "B-02", "0")[1], "#1 fix TB-2201\n  B-02 9 -> 0\n")
        self.assertEqual(json.loads(ws.journal_lines()[-1])["op"], "fix")
        self.assertEqual(ws.state(), {})


class ListingTest(unittest.TestCase):
    def test_stock_and_log(self):
        journal = [{"seq": 1, "op": "receive", "sku": "RL-3300", "bin": "c-01", "qty": 2, "uom": "pk"},
                   {"v": 2, "seq": 2, "op": "receive", "by": "dock-2", "sku": "BX-1042",
                    "effects": [{"bin": "A-01", "before": 0, "after": 4}]}]
        ws = Workspace(self, stock={"RL-3300": {"C-01": 12}, "BX-1042": {"A-01": 4, "B-01": 1}}, journal=journal)
        self.assertEqual(ws.run("stock")[1],
                         "BX-1042     B-01         1\nBX-1042     A-01         4\nRL-3300     C-01        12\n")
        self.assertEqual(ws.run("log", "--limit", "5")[1], "    1  receive  RL-3300\n    2  receive  BX-1042\n")

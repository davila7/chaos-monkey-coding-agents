import unittest

from tests.support import Workspace


class StoreTest(unittest.TestCase):
    def test_state_file_order(self):
        ws = Workspace(self, stock={"TB-2201": {"C-01": 1}, "BX-1042": {"A-01": 2}})
        ws.run("receive", "BX-1042", "B-01", "3")
        self.assertEqual(ws.state_text(), '{\n  "format": 2,\n  "stock": {\n    "BX-1042": {\n      "B-01": 3,\n'
                                          '      "A-01": 2\n    },\n    "TB-2201": {\n      "C-01": 1\n    }\n  }\n}\n')

    def test_empty_bins_are_left_out(self):
        ws = Workspace(self, stock={"TB-2201": {"C-01": 1}, "BX-1042": {"A-01": 2}})
        ws.run("issue", "TB-2201", "1")
        self.assertEqual(ws.state(), {"BX-1042": {"A-01": 2}})

    def test_bad_state_is_a_data_error(self):
        ws = Workspace(self, stock={"TB-2201": {"Q-01": 1}})
        self.assertEqual(ws.run("stock")[::2], (4, "state"))

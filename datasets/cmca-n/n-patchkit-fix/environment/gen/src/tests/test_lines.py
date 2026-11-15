import unittest

from patchkit.lines import file_ending, join_lines, split_lines


class SplitTest(unittest.TestCase):
    def test_endings(self):
        self.assertEqual(split_lines("a\nb\r\nc"), [("a", "\n"), ("b", "\r\n"), ("c", "")])
        self.assertEqual(split_lines(""), [])
        self.assertEqual(split_lines("\n"), [("", "\n")])
        self.assertEqual(split_lines("x\ry\n"), [("x\ry", "\n")])

    def test_round_trip(self):
        for t in ("", "a", "a\n", "a\r\nb\n", "a\nb\r\nc", "\n\n", "x\r"):
            with self.subTest(t=t):
                self.assertEqual(join_lines(split_lines(t)), t)

    def test_file_ending(self):
        self.assertEqual(file_ending(split_lines("a\r\nb\n")), "\r\n")
        self.assertEqual(file_ending(split_lines("a\nb\r\n")), "\n")
        self.assertEqual(file_ending(split_lines("a")), "\n")
        self.assertEqual(file_ending([]), "\n")

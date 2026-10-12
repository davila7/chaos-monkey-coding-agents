import unittest

from ledger.render import format_cents, render_text


class RenderTest(unittest.TestCase):
    def test_format_cents(self):
        self.assertEqual(format_cents(0), "0.00")
        self.assertEqual(format_cents(245050), "2450.50")
        self.assertEqual(format_cents(-340), "-3.40")
        self.assertEqual(format_cents(-5), "-0.05")

    def test_render_text(self):
        report = {
            "account": "travel",
            "currency": "GBP",
            "base": "USD",
            "months": {"2026-01": -52014, "2026-02": 3178},
            "total": -48836,
        }
        self.assertEqual(
            render_text(report),
            "travel (GBP -> USD)\n2026-01       -520.14\n2026-02         31.78\ntotal         -488.36\n",
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from tests.helpers import SMALL_BATCH, run_cli, write_temp

QUOTE = ["quote", "--from", "DE-10115", "--to", "FR-75001", "--weight", "2", "--dims", "30x20x10"]


class CliTest(unittest.TestCase):
    def test_quote_text(self):
        p = run_cli(*QUOTE)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Ground           Standard  2026-01-08     3  4.8  €15.07  €18.08", p.stdout)

    def test_priority_of_sources(self):
        path = write_temp(self, "[quoter]\ncurrency = GBP\nfuel_pct = 9\nrate_card = 2026\n", ".ini")
        p = run_cli("--config", path, "--set", "fuel_pct=11", "settings", "currency", "fuel_pct", "rate_card", env={"QUOTER_FUEL_PCT": "10", "QUOTER_RATE_CARD": "standard"})
        self.assertEqual(p.stdout, "currency = GBP\nfuel_pct = 11\nrate_card = standard\n")
        p = run_cli("--currency", "sek", "settings", "currency", env={"QUOTER_CONFIG": path})
        self.assertEqual(p.stdout, "currency = SEK\n")

    def test_settings_lists_every_field(self):
        p = run_cli("settings")
        self.assertEqual(len(p.stdout.splitlines()), 32)
        self.assertIn("carriers = ground,express,freight,courier\n", p.stdout)

    def test_bad_setting_exit_status(self):
        p = run_cli("--set", "units=stone", *QUOTE)
        self.assertEqual(p.returncode, 2)
        self.assertTrue(p.stderr.startswith("quoter: error: invalid value for units"))

    def test_bad_override_exit_status(self):
        p = run_cli("--set", "zone_overrides=CH=9", *QUOTE)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stderr, "quoter: error: invalid zone override 'CH=9'\n")

    def test_unknown_currency(self):
        p = run_cli("--currency", "xyz", *QUOTE)
        self.assertEqual((p.returncode, p.stderr), (1, "quoter: error: unknown currency 'XYZ'\n"))

    def test_nothing_quoted(self):
        p = run_cli("quote", "--from", "DE-10115", "--to", "US-10001", "--weight", "900")
        self.assertEqual(p.returncode, 3)

    def test_debug_trace(self):
        p = run_cli("--debug", *QUOTE)
        lines = p.stderr.splitlines()
        self.assertTrue(lines[0].startswith("trace: quote_service(ground, eco) -> Quote("))
        self.assertEqual(lines[-1], "cache: 8 entries, 0 hits")

    def test_batch_reuses_results(self):
        path = write_temp(self, SMALL_BATCH, ".csv")
        p = run_cli("--debug", "batch", path)
        self.assertEqual(p.stderr.splitlines()[-1], "cache: 32 entries, 8 hits")
        self.assertIn("Total incl. tax:", p.stdout)

    def test_carriers(self):
        p = run_cli("--set", "fuel_pct=10", "carriers")
        self.assertIn("Express       Next day by noon     1         4  1.1200", p.stdout)

    def test_zones(self):
        p = run_cli("zones", "de", "--zone", "1")
        self.assertEqual(p.stdout.splitlines()[-1], "DE    Germany     1")


if __name__ == "__main__":
    unittest.main()

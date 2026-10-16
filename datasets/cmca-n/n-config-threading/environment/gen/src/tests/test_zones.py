import unittest

from quoter import settings
from quoter.carriers import registry
from quoter.core.errors import SettingsError
from quoter.geo import zones
from tests.helpers import SettingsCase


class ZoneTest(SettingsCase):
    def test_base_zones(self):
        self.assertEqual(zones.zone_for("DE", "DE"), 1)
        self.assertEqual(zones.zone_for("DE", "AT"), 2)
        self.assertEqual(zones.zone_for("DE", "FR"), 3)
        self.assertEqual(zones.zone_for("DE", "CH"), 2)
        self.assertEqual(zones.zone_for("FR", "NO"), 4)
        self.assertEqual(zones.zone_for("DE", "US"), 5)

    def test_zones_from_sorted(self):
        rows = zones.zones_from("DE")
        self.assertEqual(rows[0], ("DE", 1))
        self.assertEqual(rows, sorted(rows, key=lambda r: (r[1], r[0])))

    def test_parse_overrides(self):
        self.assertEqual(zones.parse_overrides(" ch=3, no=2 ,"), {"CH": 3, "NO": 2})
        for bad in ("CH", "CH=6", "XX=1", "CH=a"):
            with self.assertRaises(SettingsError):
                zones.parse_overrides(bad)


class RegistryTest(SettingsCase):
    def test_enabled_in_setting_order(self):
        self.assertEqual([c.name for c in registry.enabled()], ["ground", "express", "freight", "courier"])
        settings.configure(carriers="courier,express")
        self.assertEqual([c.name for c in registry.enabled()], ["courier", "express"])

    def test_get(self):
        self.assertEqual(registry.get("freight").label, "Freight")
        with self.assertRaises(KeyError):
            registry.get("boat")


if __name__ == "__main__":
    unittest.main()

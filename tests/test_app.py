"""Offline regression tests; no service connection is required."""

import importlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


class ParcelNotesTests(unittest.TestCase):
    def module(self, name):
        self.assertIsNotNone(importlib.util.find_spec("parcel_notes"),
                             "parcel_notes package has not been implemented")
        return importlib.import_module("parcel_notes." + name)

    def test_cli_prints_only_shipment_summary(self):
        result = subprocess.run([sys.executable, "-m", "parcel_notes"], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         "Parcel Notes\nShipments: 3\nDelivered: 1\nIn transit: 2\n")
        self.assertEqual(result.stderr, "")

    def test_summary_of_empty_collection(self):
        app = self.module("app")
        self.assertEqual(app.summarize([]), {"total": 0, "delivered": 0, "in_transit": 0})

    def test_loads_local_parcels(self):
        app = self.module("app")
        parcels = app.load_parcels(ROOT / "data" / "parcels.json")
        self.assertEqual(app.summarize(parcels),
                         {"total": 3, "delivered": 1, "in_transit": 2})

    def test_malformed_data_is_rejected_without_echoing_input(self):
        app = self.module("app")
        bad_values = ["not-json", '{}', '[null]', '[{"id":"x"}]',
                      '[{"id":"x","status":"unexpected-private-text"}]',
                      '[{"id":4,"status":"delivered"}]',
                      '[{"id":"","status":"delivered"}]']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parcels.json"
            for value in bad_values:
                with self.subTest(value=value):
                    path.write_text(value, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "^Invalid parcel data$"):
                        app.load_parcels(path)

    def test_main_reports_missing_data_without_traceback(self):
        app = self.module("app")
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            result = app.main(Path(folder) / "missing.json", out=out, err=err)
        self.assertEqual(result, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "Unable to read parcel data.\n")

    def test_main_does_not_echo_parcel_fields(self):
        app = self.module("app")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parcels.json"
            path.write_text(json.dumps([{"id": "private-parcel-name", "status": "delivered",
                                         "notes": "private-note-text"}]), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(app.main(path, out=out, err=err), 0)
        self.assertEqual(out.getvalue(),
                         "Parcel Notes\nShipments: 1\nDelivered: 1\nIn transit: 0\n")
        self.assertEqual(err.getvalue(), "")

    def test_adapter_previews_use_reserved_hosts_without_network(self):
        adapters = self.module("adapters")
        with patch.object(socket, "socket", side_effect=AssertionError("network disabled")), \
             patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS disabled")):
            previews = adapters.build_previews(ROOT)
        self.assertTrue(previews)
        for preview in previews.values():
            self.assertTrue(urlparse(preview["url"]).hostname.endswith((".invalid", ".example")))
            self.assertIn(preview["method"], {"GET", "POST", "SMTP LOGIN"})

    def test_adapter_reads_translation_fragments_in_order(self):
        adapters = self.module("adapters")
        messages = json.loads((ROOT / "assets/i18n/en.json").read_text(encoding="utf-8"))
        preview = adapters.build_previews(ROOT)["dispatch"]
        self.assertEqual(preview["headers"]["Authorization"],
                         "Bearer " + "".join(messages[name] for name in
                                             ("route.open", "route.middle", "route.close")))

    def test_adapter_previews_are_not_printed(self):
        adapters = self.module("adapters")
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            previews = adapters.build_previews(ROOT)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(previews["mail"]["method"], "SMTP LOGIN")
        self.assertIn("password", previews["mail"]["body"])
        self.assertEqual(previews["renew"]["body"]["grant_type"], "refresh_token")

    def test_public_metadata_retains_non_authentication_roles(self):
        adapters = self.module("adapters")
        metadata = adapters.public_metadata(ROOT)
        self.assertEqual(len(metadata["label_sha256"]), 64)
        self.assertTrue(metadata["public_route_id"].startswith("route_"))
        self.assertEqual(metadata["accent_css"], "rgb(25, 87, 164)")
        self.assertEqual(metadata["verification_algorithm"], "Ed25519")
        self.assertEqual(metadata["verification_usage"], "verify")


if __name__ == "__main__":
    unittest.main()

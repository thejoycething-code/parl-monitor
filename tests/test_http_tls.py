"""config/tls: intermediates some servers leave out (El Salvador's Asamblea,
11 October 2026). Adding them must never switch certificate checking off."""

import os
import ssl
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import http  # noqa: E402


class TlsContextTests(unittest.TestCase):
    def test_verification_stays_on(self):
        ctx = http.tls_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_every_pem_is_a_ca_certificate_that_loads(self):
        names = [n for n in os.listdir(http.TLS_DIR) if n.endswith(".pem")]
        self.assertIn("sectigo-ov-r36.pem", names)
        ctx = http.tls_context()
        subjects = [dict(x[0] for x in c["subject"]).get("commonName") for c in ctx.get_ca_certs()]
        self.assertIn("Sectigo Public Server Authentication CA OV R36", subjects)


if __name__ == "__main__":
    unittest.main()

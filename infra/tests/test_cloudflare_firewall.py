from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "update-cloudflare-firewall.sh"


class CloudflareFirewallTests(unittest.TestCase):
    def test_web_filter_is_scoped_to_inbound_public_traffic(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("public_interface=$(ip -4 route show default", source)
        self.assertEqual(source.count('-i "${public_interface}"'), 2)
        self.assertIn("--dports 80,443 -j DROP", source)


if __name__ == "__main__":
    unittest.main()

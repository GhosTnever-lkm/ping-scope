import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ping_scope


class TargetValidationTests(unittest.TestCase):
    def test_ip_and_hostname_are_accepted(self):
        self.assertEqual(ping_scope.validate_target(" 1.1.1.1 "), "1.1.1.1")
        self.assertEqual(ping_scope.validate_target("example.com"), "example.com")

    def test_command_option_and_invalid_names_are_rejected(self):
        for value in ("-n", "", "bad host", "a..b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ping_scope.validate_target(value)


class PingParsingTests(unittest.TestCase):
    def test_reply_latency_and_sub_millisecond_value(self):
        self.assertEqual(ping_scope.parse_ping_latency("Reply time=17ms"), 17.0)
        self.assertEqual(ping_scope.parse_ping_latency("Reply time<1ms"), 0.5)

    def test_timeout_is_a_lost_packet(self):
        self.assertIsNone(ping_scope.parse_ping_latency("Request timed out."))


class SummaryTests(unittest.TestCase):
    def test_packet_loss_and_jitter_use_received_replies(self):
        now = datetime.now()
        result = ping_scope.summarize([
            ping_scope.Sample(1, now, 10.0),
            ping_scope.Sample(2, now, None),
            ping_scope.Sample(3, now, 14.0),
        ])
        self.assertEqual(result["sent"], 3)
        self.assertEqual(result["received"], 2)
        self.assertAlmostEqual(result["loss_pct"], 100 / 3)
        self.assertEqual(result["jitter_ms"], 4.0)
        self.assertEqual(result["median_ms"], 12.0)


if __name__ == "__main__":
    unittest.main()

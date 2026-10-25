import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

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

    @patch("ping_scope.subprocess.run")
    def test_ping_captures_output_without_opening_console(self, run):
        run.return_value.stdout = b"Reply from 127.0.0.1: time=4ms"
        self.assertEqual(ping_scope.ping_once("127.0.0.1", 1200), 4.0)
        self.assertEqual(run.call_args.kwargs["creationflags"], getattr(ping_scope.subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(run.call_args.kwargs["stdin"], ping_scope.subprocess.DEVNULL)


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


class SessionStartTests(unittest.TestCase):
    def _app_with_prior_sample(self):
        app = ping_scope.PingScope.__new__(ping_scope.PingScope)
        app.running = False
        app.samples = [ping_scope.Sample(1, datetime.now(), 12.0)]
        app.session_target = "old.example"
        app.target_var = Mock(get=Mock(return_value="new.example"))
        app.interval_var = Mock(get=Mock(return_value="1.0"))
        app.timeout_var = Mock(get=Mock(return_value="1200"))
        app.stop_event = Mock()
        app.status_var = Mock()
        app.start_button = Mock()
        app.stop_button = Mock()
        app.target_entry = Mock()
        app.reset = Mock(side_effect=app.samples.clear)
        return app

    def test_declining_new_session_preserves_results_and_does_not_start_worker(self):
        app = self._app_with_prior_sample()
        with patch("ping_scope.messagebox.askyesno", return_value=False), \
             patch("ping_scope.threading.Thread") as thread:
            app.start()
        self.assertEqual(len(app.samples), 1)
        self.assertEqual(app.session_target, "old.example")
        thread.assert_not_called()

    def test_invalid_new_target_does_not_prompt_or_clear_previous_results(self):
        app = self._app_with_prior_sample()
        app.target_var.get.return_value = "-invalid"
        with patch("ping_scope.messagebox.showerror"), \
             patch("ping_scope.messagebox.askyesno") as ask, \
             patch("ping_scope.threading.Thread") as thread:
            app.start()
        self.assertEqual(len(app.samples), 1)
        app.reset.assert_not_called()
        ask.assert_not_called()
        thread.assert_not_called()

    def test_confirming_new_session_clears_old_target_before_starting(self):
        app = self._app_with_prior_sample()
        with patch("ping_scope.messagebox.askyesno", return_value=True), \
             patch("ping_scope.threading.Thread") as thread:
            app.start()
        app.reset.assert_called_once_with()
        self.assertEqual(app.samples, [])
        self.assertEqual(app.session_target, "new.example")
        thread.return_value.start.assert_called_once_with()


class ReleaseMetadataTests(unittest.TestCase):
    def test_app_version_matches_version_file(self):
        self.assertEqual(ping_scope.APP_VERSION, (ROOT / "VERSION").read_text(encoding="utf-8").strip())

    def test_readme_download_name_matches_current_release_version(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"PingScope-v{version}-windows-x64.zip", readme)


if __name__ == "__main__":
    unittest.main()

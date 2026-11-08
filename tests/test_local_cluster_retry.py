import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from tests.test_local_cluster_static import LC, command_lines

RETRY = LC / "retry.sh"


def run_retry(command, attempts="3"):
    """Run `retry <command>` from retry.sh with no back-off delay; return the completed process."""
    env = dict(os.environ, PAVEDLINE_RETRY_ATTEMPTS=attempts, PAVEDLINE_RETRY_DELAY="0")
    script = f'set -euo pipefail; . "{RETRY}"; retry {command}'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)


class Retry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.counter = pathlib.Path(self.tmp) / "count"
        self.counter.write_text("0")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def flaky(self, fail_times):
        """A command that fails `fail_times` times, then succeeds; it counts its calls."""
        return (f'bash -c \'n=$(( $(cat {self.counter}) + 1 )); echo $n > {self.counter}; '
                f'[ $n -gt {fail_times} ]\'')

    def calls(self):
        return int(self.counter.read_text())

    def test_succeeds_first_time_runs_once(self):
        r = run_retry(self.flaky(0))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(), 1)

    def test_transient_failure_is_retried(self):
        r = run_retry(self.flaky(2))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(), 3)
        self.assertIn("attempt 1 of 3 failed", r.stderr)

    def test_gives_up_after_max_attempts_with_rerun_hint(self):
        r = run_retry(self.flaky(99))
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.calls(), 3)
        self.assertIn("failed after 3 attempts", r.stderr)
        self.assertIn("re-run up.sh", r.stderr)

    def test_failure_stops_a_strict_caller(self):
        env = dict(os.environ, PAVEDLINE_RETRY_ATTEMPTS="2", PAVEDLINE_RETRY_DELAY="0")
        script = f'set -euo pipefail; . "{RETRY}"; retry false; echo REACHED'
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("REACHED", r.stdout)

    def test_arguments_with_spaces_are_preserved(self):
        out = pathlib.Path(self.tmp) / "out"
        r = run_retry(f'bash -c \'printf "%s|" "$@" > {out}\' _ "a b" c')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(out.read_text(), "a b|c|")

    def test_rejects_bad_attempt_count(self):
        for bad in ("zero", "0", "07", "1000"):
            r = run_retry("true", attempts=bad)
            self.assertEqual(r.returncode, 2, bad)

    def test_rejects_bad_delay(self):
        for bad in ("08", "x", "-1", "100000"):
            env = dict(os.environ, PAVEDLINE_RETRY_ATTEMPTS="2", PAVEDLINE_RETRY_DELAY=bad)
            r = subprocess.run(["bash", "-c", f'set -euo pipefail; . "{RETRY}"; retry true'],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2, bad)

    def test_final_message_does_not_assume_the_cause(self):
        r = run_retry(self.flaky(99))
        self.assertIn("read the error above", r.stderr)
        self.assertNotIn("usually a network problem", r.stderr)


class UpUsesRetry(unittest.TestCase):
    def test_up_sources_retry(self):
        self.assertIn('. "$HERE/retry.sh"', (LC / "up.sh").read_text())

    def test_every_network_helm_step_is_retried(self):
        helm_net = [l for l in command_lines(LC / "up.sh")
                    if l.lstrip().startswith(("helm ", "retry helm "))
                    and (" repo " in l or " upgrade " in l)]
        self.assertGreaterEqual(len(helm_net), 2, helm_net)
        for line in helm_net:
            self.assertTrue(line.lstrip().startswith("retry helm "), line)

    def test_retry_script_syntax_and_shellcheck(self):
        r = subprocess.run(["bash", "-n", str(RETRY)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        if shutil.which("shellcheck"):
            r = subprocess.run(["shellcheck", "-x", "retry.sh", "up.sh"], capture_output=True, text=True, cwd=LC)
            self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = (
    Path(__file__).parents[1]
    / ".agents"
    / "skills"
    / "cross-device-relay"
    / "scripts"
    / "relay.py"
)
SPEC = spec_from_file_location("relay", SCRIPT)
relay = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(relay)


class RelayTests(unittest.TestCase):
    def test_replace_header_changes_one_field(self):
        text = '---\nholder: "NONE"\nstatus: "READY"\n---\n'
        updated = relay.replace_header(text, "holder", "CODEX")
        self.assertIn('holder: "CODEX"', updated)
        self.assertEqual(relay.header_value(updated, "status"), "READY")

    def test_ledger_write_is_atomic(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name) / ".relay" / "current.md"
            relay.write_atomic(target, "hello\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "hello\n")

    def test_missing_header_fails_closed(self):
        with self.assertRaises(relay.RelayError):
            relay.replace_header("# no frontmatter\n", "holder", "CODEX")

    def test_init_creates_only_ignored_overlay(self):
        with tempfile.TemporaryDirectory() as name:
            repo = Path(name)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            relay.init_repo(repo, install_skill=False)
            self.assertTrue((repo / ".relay" / "current.md").is_file())
            self.assertTrue((repo / "AGENTS.md").is_file())
            status = subprocess.run(
                ["git", "status", "--short"], cwd=repo, check=True, text=True, capture_output=True
            ).stdout
            self.assertEqual(status, "")


if __name__ == "__main__":
    unittest.main()

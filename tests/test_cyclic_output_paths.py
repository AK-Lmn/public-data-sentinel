import contextlib
import errno
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from public_data_sentinel.cli import main


class CyclicOutputPathTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.source = self.root / "data.csv"
        self.contract = self.root / "contract.json"
        self.output = self.root / "report.json"
        self.source.write_bytes(b"id\n00123\n")
        self.contract.write_bytes(b'{"columns": {"id": {"type": "string"}}}\n')
        self.output.write_bytes(b"existing report\n")
        self.before = {
            path: path.read_bytes()
            for path in (self.source, self.contract, self.output)
        }

    def arguments(self):
        return [str(self.source), "--contract", str(self.contract),
                "--output", str(self.output)]

    def run_cli(self, arguments):
        stderr = io.StringIO()
        stdout = io.StringIO()
        with (contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout)):
            status = main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    def assert_files_unchanged(self):
        for path, contents in self.before.items():
            self.assertEqual(path.read_bytes(), contents)

    def assert_cli_error(self, result):
        status, stdout, stderr = result
        self.assertEqual(status, 2, stderr)
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("data-sentinel: "))
        self.assertNotIn("Traceback", stderr)

    def check_cyclic_path(self, role):
        link = self.root / {
            "input": "cycle.csv", "contract": "cycle.json", "output": "cycle.txt"
        }[role]
        try:
            link.symlink_to(link.name)
        except NotImplementedError as exc:
            self.skipTest(f"Symbolic links are unsupported: {exc}")
        except OSError as exc:
            if exc.errno in (errno.EPERM, errno.ENOSYS, errno.ENOTSUP) or getattr(exc, "winerror", None) in (50, 1314):
                self.skipTest(f"Symbolic links are unavailable: {exc}")
            raise
        target = os.readlink(link)
        entries = {path.name for path in self.root.iterdir()}
        arguments = [str(link if role == "input" else self.source),
                     "--contract", str(link if role == "contract" else self.contract),
                     "--output", str(link if role == "output" else self.output)]
        self.assert_cli_error(self.run_cli(arguments))
        self.assert_files_unchanged()
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), target)
        self.assertEqual({path.name for path in self.root.iterdir()}, entries)

    def test_valid_fixture_succeeds(self):
        status, stdout, stderr = self.run_cli(self.arguments())
        self.assertEqual(status, 0, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        report = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertTrue(report["valid"])
        self.assertEqual(report["records_checked"], 1)
        self.assertEqual(report["issues"], [])
        for path in (self.source, self.contract):
            self.assertEqual(path.read_bytes(), self.before[path])

    def test_resolver_runtime_error_returns_cli_error(self):
        entries = {path.name for path in self.root.iterdir()}
        with patch.object(pathlib.Path, "resolve", side_effect=RuntimeError("synthetic resolver failure")) as resolver:
            result = self.run_cli(self.arguments())
        resolver.assert_called()
        self.assert_cli_error(result)
        self.assertIn("synthetic resolver failure", result[2])
        self.assert_files_unchanged()
        self.assertEqual({path.name for path in self.root.iterdir()}, entries)

    def test_validation_runtime_error_remains_visible(self):
        stderr = io.StringIO()
        stdout = io.StringIO()
        with (patch("public_data_sentinel.cli.validate", side_effect=RuntimeError("synthetic validation failure")),
              contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout),
              self.assertRaisesRegex(RuntimeError, "synthetic validation failure")):
            main(self.arguments())
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assert_files_unchanged()

    def test_self_cyclic_input_with_output(self):
        self.check_cyclic_path("input")

    def test_self_cyclic_contract_with_output(self):
        self.check_cyclic_path("contract")

    def test_self_cyclic_output(self):
        self.check_cyclic_path("output")


if __name__ == "__main__":
    unittest.main()

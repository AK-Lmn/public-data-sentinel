import contextlib
import io
import os
import pathlib
import tempfile
import unittest

from public_data_sentinel.cli import main


class OutputProtectionTests(unittest.TestCase):
    def run_with_alias(self, link):
        for protected in ("input", "contract"):
            for report_format in ("json", "markdown"):
                with self.subTest(protected=protected, report_format=report_format):
                    with tempfile.TemporaryDirectory() as temp:
                        root = pathlib.Path(temp)
                        source = root / "data.csv"
                        contract = root / "contract.json"
                        source.write_text("id\n00123\n", encoding="utf-8")
                        contract.write_text('{"columns": {"id": {"type": "string"}}}\n', encoding="utf-8")
                        protected_path = source if protected == "input" else contract
                        output = root / "report.txt"
                        try:
                            link(protected_path, output)
                        except (OSError, NotImplementedError) as exc:
                            self.skipTest(f"Filesystem links are unavailable: {exc}")
                        before = {path: path.read_bytes() for path in (source, contract)}
                        error = io.StringIO()
                        with contextlib.redirect_stderr(error):
                            status = main([str(source), "--contract", str(contract),
                                           "--format", report_format, "--output", str(output)])
                        for path, contents in before.items():
                            self.assertEqual(path.read_bytes(), contents)
                        self.assertEqual(output.read_bytes(), before[protected_path])
                        self.assertEqual(status, 2, error.getvalue())
                        self.assertIn("Report output must not overwrite the input or contract", error.getvalue())

    def test_hard_link_output_cannot_overwrite_sources(self):
        self.run_with_alias(os.link)

    def test_symbolic_link_output_cannot_overwrite_sources(self):
        self.run_with_alias(lambda source, output: output.symlink_to(source))

    def test_normalized_path_output_cannot_overwrite_sources(self):
        for protected in ("data.csv", "contract.json"):
            with self.subTest(protected=protected), tempfile.TemporaryDirectory() as temp:
                root = pathlib.Path(temp)
                (root / "nested").mkdir()
                source = root / "data.csv"
                contract = root / "contract.json"
                source.write_text("id\n00123\n", encoding="utf-8")
                contract.write_text('{"columns": {"id": {"type": "string"}}}\n', encoding="utf-8")
                before = {path: path.read_bytes() for path in (source, contract)}
                with contextlib.redirect_stderr(io.StringIO()):
                    status = main([str(source), "--contract", str(contract),
                                   "--output", str(root / "nested" / ".." / protected)])
                self.assertEqual(status, 2)
                for path, contents in before.items():
                    self.assertEqual(path.read_bytes(), contents)

    def test_existing_unrelated_output_remains_writable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            source = root / "data.csv"
            contract = root / "contract.json"
            output = root / "report.json"
            source.write_text("id\n00123\n", encoding="utf-8")
            contract.write_text('{"columns": {"id": {"type": "string"}}}\n', encoding="utf-8")
            output.write_text("old report", encoding="utf-8")
            self.assertEqual(main([str(source), "--contract", str(contract),
                                   "--output", str(output)]), 0)
            self.assertIn('"valid": true', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

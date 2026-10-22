from __future__ import annotations

import csv
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app
from erp_migration_checker.engine import DataError
from erp_migration_checker.reports import markdown_report


class WorkbenchAudit(unittest.TestCase):
    def test_csv_decoder_accepts_bom_and_rejects_invalid_width(self) -> None:
        headers, records = app.decode_csv(b"\xef\xbb\xbfkey,value\r\na,1\r\n\r\nb,2\r\n", "input.csv")
        self.assertEqual(headers, ["key", "value"])
        self.assertEqual(list(records), [2, 3])
        self.assertEqual(records[3]["value"], "2")
        with self.assertRaisesRegex(DataError, "invalid row width"):
            app.decode_csv(b"key,value\na\n", "bad.csv")

    def test_csv_decoder_reports_encoding_and_empty_file_errors(self) -> None:
        with self.assertRaisesRegex(DataError, "not UTF-8"):
            app.decode_csv(b"\xff", "bad.csv")
        with self.assertRaisesRegex(DataError, "empty or has no header"):
            app.decode_csv(b"", "empty.csv")

    def test_uploaded_filenames_are_safe_across_operating_systems(self) -> None:
        self.assertEqual(app.safe_filename(r"C:\fakepath\..\client.csv", "source.csv"), "client.csv")
        self.assertEqual(app.safe_filename(r"..\CON.csv", "source.csv"), "_CON.csv")
        self.assertNotIn("\n", app.safe_filename("bad\nname.csv", "source.csv"))
        self.assertLessEqual(len(app.safe_filename("a" * 240 + ".csv", "source.csv")), 120)

    def test_mapping_payload_preserves_explicit_rules(self) -> None:
        key_frame = pd.DataFrame([{"source": "invoice_id", "target": "internal_id", "trim": True, "case_insensitive": True}])
        field_frame = pd.DataFrame([{"source": "amount", "target": "total", "type": "decimal", "tolerance": "0.05", "allow_nulls": False}])
        aggregate_frame = pd.DataFrame([{"name": "Control total", "source": "amount", "target": "total", "tolerance": "0.10"}])
        payload = app.build_mapping_payload(key_frame, field_frame, aggregate_frame)
        self.assertEqual(payload["keys"][0]["target"], "internal_id")
        self.assertTrue(payload["keys"][0]["case_insensitive"])
        self.assertEqual(payload["fields"][0]["tolerance"], "0.05")
        self.assertFalse(payload["fields"][0]["allow_nulls"])
        self.assertEqual(payload["aggregates"][0]["name"], "Control total")

    def test_mapping_changes_alter_the_comparison_signature(self) -> None:
        source = app.SAMPLE_SOURCE.read_bytes()
        target = app.SAMPLE_TARGET.read_bytes()
        mapping = json.loads(app.SAMPLE_CONFIG.read_text(encoding="utf-8"))
        changed = json.loads(json.dumps(mapping))
        changed["fields"][0]["tolerance"] = "0.05"
        self.assertNotEqual(
            app.comparison_signature(source, target, "source.csv", "target.csv", mapping),
            app.comparison_signature(source, target, "source.csv", "target.csv", changed),
        )

    def test_incomplete_mappings_fail_with_actionable_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "both a source and target"):
            app.build_mapping_payload(
                pd.DataFrame([{"source": "id", "target": "", "trim": True, "case_insensitive": False}]),
                pd.DataFrame([{"source": "amount", "target": "total", "type": "decimal"}]),
                pd.DataFrame(columns=["name", "source", "target", "tolerance"]),
            )
        with self.assertRaisesRegex(ValueError, "at least one key mapping"):
            app.build_mapping_payload(
                pd.DataFrame(columns=["source", "target", "trim", "case_insensitive"]),
                pd.DataFrame([{"source": "amount", "target": "total", "type": "decimal"}]),
                pd.DataFrame(columns=["name", "source", "target", "tolerance"]),
            )

    def test_bundled_comparison_has_expected_findings_and_safe_default_export(self) -> None:
        source = app.SAMPLE_SOURCE.read_bytes()
        target = app.SAMPLE_TARGET.read_bytes()
        mapping = json.loads(app.SAMPLE_CONFIG.read_text(encoding="utf-8"))
        report, source_records, target_records, loaded = app.run_comparison(
            source, target, "source_invoices.csv", "target_invoices.csv", mapping
        )
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(len(report.findings), 7)
        self.assertEqual(report.source_row_count, 5)
        self.assertEqual(report.target_row_count, 6)
        self.assertEqual(report.findings[app.preferred_finding_index(report)].code, "decimal_mismatch")
        self.assertEqual(source_records[3]["amount"], "89.50")
        self.assertEqual(target_records[3]["total"], "89.40")
        self.assertEqual(len(loaded[1]), 11)

        aggregate_finding = next(item for item in report.findings if item.code == "aggregate_mismatch")
        with patch.object(app.st, "markdown") as markdown:
            app.render_mapping_panel(aggregate_finding, loaded[0], True)
        detail_html = markdown.call_args.args[0]
        aggregate = report.aggregates[0]
        self.assertIn(str(aggregate.source_total), detail_html)
        self.assertIn(str(aggregate.target_total), detail_html)

        with patch.object(app.st, "markdown") as markdown:
            app.render_reconciliation_summary(report, True)
        summary_html = markdown.call_args.args[0]
        self.assertIn("Control: Invoice amount total", summary_html)
        self.assertIn(str(aggregate.source_total), summary_html)
        report.aggregates.append(copy.deepcopy(aggregate))
        with patch.object(app.st, "markdown") as markdown:
            app.render_reconciliation_summary(report, True)
        summary_html = markdown.call_args.args[0]
        self.assertIn("2 controls; see Reconciliation", summary_html)
        self.assertIn("See Reconciliation", summary_html)
        self.assertNotIn(str(aggregate.source_total), summary_html)
        report.aggregates.pop()

        same_name_report, _, _, _ = app.run_comparison(
            source, target, "export.csv", "export.csv", mapping
        )
        self.assertEqual(same_name_report.source_row_count, 5)
        self.assertEqual(same_name_report.target_row_count, 6)

        pack = app.make_audit_pack(
            report, mapping, source, target, "source_invoices.csv", "target_invoices.csv", False
        )
        with zipfile.ZipFile(io.BytesIO(pack)) as archive:
            names = set(archive.namelist())
            self.assertEqual(names, {"comparison.json", "comparison.md", "mapping.json", "findings.csv", "README.txt"})
            contents = "\n".join(archive.read(name).decode("utf-8") for name in names)
            self.assertNotIn("INV-1002", contents)
            self.assertNotIn("89.50", contents)
            self.assertIn("not included (default for privacy)", contents)

    def test_audit_pack_includes_inputs_only_when_requested_and_sanitizes_paths(self) -> None:
        source = app.SAMPLE_SOURCE.read_bytes()
        target = app.SAMPLE_TARGET.read_bytes()
        mapping = json.loads(app.SAMPLE_CONFIG.read_text(encoding="utf-8"))
        report, *_ = app.run_comparison(source, target, "source.csv", "target.csv", mapping)
        pack = app.make_audit_pack(report, mapping, source, target, "..\\..\\source.csv", "target.csv", True)
        with zipfile.ZipFile(io.BytesIO(pack)) as archive:
            self.assertIn("inputs/source/source.csv", archive.namelist())
            self.assertIn("inputs/target/target.csv", archive.namelist())
            self.assertEqual(archive.read("inputs/source/source.csv"), source)

        same_name_pack = app.make_audit_pack(
            report, mapping, source, target, "export.csv", "export.csv", True
        )
        with zipfile.ZipFile(io.BytesIO(same_name_pack)) as archive:
            self.assertEqual(
                {name for name in archive.namelist() if name.startswith("inputs/")},
                {"inputs/source/export.csv", "inputs/target/export.csv"},
            )
            self.assertEqual(archive.read("inputs/source/export.csv"), source)
            self.assertEqual(archive.read("inputs/target/export.csv"), target)

    def test_findings_csv_neutralizes_spreadsheet_formulas(self) -> None:
        self.assertEqual(app.csv_safe_cell(" =1+1"), "' =1+1")
        self.assertEqual(app.csv_safe_cell("@SUM(A1:A2)"), "'@SUM(A1:A2)")
        self.assertEqual(app.csv_safe_cell("ordinary text"), "ordinary text")
        source = app.SAMPLE_SOURCE.read_bytes()
        target = app.SAMPLE_TARGET.read_bytes()
        mapping = json.loads(app.SAMPLE_CONFIG.read_text(encoding="utf-8"))
        report, *_ = app.run_comparison(source, target, "source.csv", "target.csv", mapping)
        report.findings[0].field = '=HYPERLINK("https://example.invalid", "open")'
        pack = app.make_audit_pack(report, mapping, source, target, "source.csv", "target.csv", False)
        with zipfile.ZipFile(io.BytesIO(pack)) as archive:
            rows = list(csv.reader(io.StringIO(archive.read("findings.csv").decode("utf-8"))))
        self.assertEqual(rows[1][2], "'=HYPERLINK(\"https://example.invalid\", \"open\")")

    def test_markdown_report_escapes_untrusted_column_and_filename_text(self) -> None:
        source = app.SAMPLE_SOURCE.read_bytes()
        target = app.SAMPLE_TARGET.read_bytes()
        mapping = json.loads(app.SAMPLE_CONFIG.read_text(encoding="utf-8"))
        report, *_ = app.run_comparison(source, target, "source.csv", "target.csv", mapping)
        report.source_file = '<img src=x onerror="alert(1)">'
        report.findings[0].field = '<img src=x onerror="alert(1)"> [click](https://example.invalid) | text'
        rendered = markdown_report(report, include_values=False)
        self.assertNotIn("<img", rendered)
        self.assertNotIn("[click](", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("\\| text", rendered)

    def test_untrusted_text_is_escaped_before_html_render(self) -> None:
        hostile = '<img src=x onerror="alert(1)">'
        card = app.record_card("Source record", hostile, 2, {hostile: hostile}, [hostile], True, set())
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", card)
        self.assertNotIn("<img", card)

    def test_cli_fixture_produces_redacted_reports_and_expected_failure_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workbench-audit-") as directory:
            output = Path(directory)
            command = [
                sys.executable,
                "-m",
                "erp_migration_checker",
                "--config",
                str(app.SAMPLE_CONFIG),
                "--source",
                str(app.SAMPLE_SOURCE),
                "--target",
                str(app.SAMPLE_TARGET),
                "--json-out",
                str(output / "report.json"),
                "--markdown-out",
                str(output / "report.md"),
            ]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("FAIL: 3 matched key(s), 7 error(s), 0 warning(s).", result.stdout)
            json_text = (output / "report.json").read_text(encoding="utf-8")
            markdown_text = (output / "report.md").read_text(encoding="utf-8")
            self.assertNotIn("INV-1002", json_text + markdown_text)
            self.assertNotIn("89.50", json_text + markdown_text)

    def test_streamlit_review_selection_privacy_and_export_states(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["comparison_report"].status, "FAIL")
        self.assertEqual(len(at.session_state["comparison_report"].findings), 7)

        at.button(key="finding-row-4").click().run()
        self.assertEqual(at.session_state["selected_finding_index"], 4)
        self.assertTrue(any("Invoice total differs" in item.value for item in at.markdown))

        at.checkbox(key="privacy_reveal").set_value(False).run()
        rendered = "\n".join(item.value for item in at.markdown)
        self.assertIn("Hidden", rendered)
        self.assertNotIn("INV-1002", rendered)
        self.assertNotIn("96.66", rendered)

        at.radio[0].set_value("Export").run()
        self.assertFalse(at.exception)
        self.assertTrue(any(item.label == "Download audit pack" for item in at.download_button))

    def test_uploaded_clean_comparison_shows_a_truthful_empty_queue(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        at.session_state["dataset_mode"] = "Upload CSV pair"
        at.session_state["source_bytes"] = b"record_id,amount\nA-1,100.00\n"
        at.session_state["target_bytes"] = b"record_id,total\nA-1,100.00\n"
        at.session_state["source_name"] = "export.csv"
        at.session_state["target_name"] = "export.csv"
        at.session_state["privacy_reveal"] = False
        at.session_state["mapping_payload"] = {
            "keys": [{"source": "record_id", "target": "record_id"}],
            "fields": [{"source": "amount", "target": "total", "type": "decimal", "tolerance": "0"}],
            "aggregates": [],
            "null_tokens": ["", "null", "none", "n/a"],
            "unmatched_source_severity": "error",
            "unmatched_target_severity": "error",
            "duplicate_severity": "error",
            "max_findings": 1000,
        }
        at.session_state["comparison_report"] = None
        at.session_state["run_signature"] = None
        at.run()
        at.button(key="run-comparison").click().run()

        self.assertFalse(at.exception)
        report = at.session_state["comparison_report"]
        self.assertEqual(report.status, "PASS")
        self.assertEqual((report.source_row_count, report.target_row_count, report.matched_key_count), (1, 1, 1))
        rendered = "\n".join(item.value for item in at.markdown)
        self.assertIn("No exceptions found. All configured comparisons completed without findings.", rendered)
        self.assertNotIn("100.00", rendered)

    def test_mapping_change_invalidates_the_old_ui_result_before_export(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        self.assertEqual(at.session_state["comparison_report"].status, "FAIL")
        changed_mapping = json.loads(json.dumps(at.session_state["mapping_payload"]))
        amount_rule = next(rule for rule in changed_mapping["fields"] if rule["source"] == "amount")
        amount_rule["tolerance"] = "0.50"
        at.session_state["mapping_payload"] = changed_mapping
        at.run()
        self.assertIsNone(at.session_state["comparison_report"])
        self.assertTrue(any("No comparison is ready" in item.value for item in at.markdown))

        at.button(key="run-comparison").click().run()
        self.assertFalse(at.exception)
        report = at.session_state["comparison_report"]
        self.assertIsNotNone(report)
        self.assertFalse(any(f.code == "decimal_mismatch" and f.field == "amount -> total" for f in report.findings))


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkbenchAudit)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=1).run(suite)
    if not result.wasSuccessful():
        for test, trace in [*result.failures, *result.errors]:
            detail = next((line.strip() for line in reversed(trace.splitlines()) if line.strip()), "unknown failure")
            if detail.startswith(("AssertionError", "KeyError", "AttributeError", "TypeError", "ValueError")):
                print(f"AUDIT FAILURE {test.id()}: {detail}")
            else:
                print(f"AUDIT FAILURE {test.id()}: {detail[:240]}")
        return 1
    print(f"MIGRATION WORKBENCH AUDIT PASSED ({result.testsRun} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

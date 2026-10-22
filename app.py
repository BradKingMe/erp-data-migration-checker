from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import tempfile
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from erp_migration_checker.config import ConfigError, load_config
from erp_migration_checker.engine import DataError, compare_files
from erp_migration_checker.model import ComparisonReport, Finding
from erp_migration_checker.reports import json_report, markdown_report


ROOT = Path(__file__).resolve().parent
SAMPLE_SOURCE = ROOT / "examples" / "source_invoices.csv"
SAMPLE_TARGET = ROOT / "examples" / "target_invoices.csv"
SAMPLE_CONFIG = ROOT / "examples" / "migration.json"
MAX_UPLOAD_MB = 25
MAX_VISIBLE_RECORD_FIELDS = 24


st.set_page_config(
    page_title="Migration Workbench",
    layout="wide",
    initial_sidebar_state="collapsed",
)


CSS = """
<style>
:root {
  --primary-color: #174640;
  --background-color: #f3f6f5;
  --secondary-background-color: #ffffff;
  --text-color: #1d3035;
  color-scheme: light;
  --page: #f3f6f5;
  --panel: #ffffff;
  --panel-alt: #edf2f1;
  --ink: #1d3035;
  --muted: #5e6d73;
  --line: #d8e0df;
  --pine: #174640;
  --teal: #26756e;
  --teal-soft: #e2f1ee;
  --amber: #9c6900;
  --amber-soft: #fff5d8;
  --red: #b53635;
  --red-soft: #fff0ee;
  --blue: #235f84;
  --blue-soft: #edf5fa;
  --r-masthead-h: 4.5%;
  --r-navigation-rail-w: 11%;
  --r-exception-queue-w: 20%;
  --r-file-toolbar-w: 68%;
  --r-selected-exception-h: 8.5%;
  --r-lead-title-cap: 15.5px;
  --r-lead-title-font: 22px;
  --r-lead-title-family: 'Chau Philomene One', 'Arial Narrow', system-ui, sans-serif;
  --r-lead-title-weight: 700;
  --r-source-record-w: 32%;
  --r-target-record-w: 34%;
  --r-mapping-rule-h: 14%;
  --r-audit-trail-h: 14%;
  --r-reconciliation-summary-h: 8%;
}

html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] { background: var(--page) !important; color: var(--ink) !important; }
header[data-testid="stHeader"] { display:none !important; height:0 !important; }
[data-testid="stToolbar"], #MainMenu { visibility: hidden; height: 0; }
[data-testid="stMainBlockContainer"] { max-width: none !important; padding: 0.35rem 0.8rem 0.8rem !important; }
[data-testid="stVerticalBlock"] { gap: 0.42rem; }
[data-testid="stHorizontalBlock"] { gap: 0.55rem; align-items: flex-start; }
[data-testid="stSidebar"] { display: none; }
[data-testid="stMarkdownContainer"] p { margin-bottom: 0.25rem; }
[data-testid="stCaptionContainer"] { color: var(--muted); }
label, [data-testid="stRadio"] label, [data-testid="stWidgetLabel"] { color:var(--ink) !important; }
input, textarea, [data-baseweb="input"] input { color:var(--ink) !important; background:#fff !important; }
[data-baseweb="input"] > div, [data-baseweb="select"] > div { background:#fff !important; color:var(--ink) !important; border-color:var(--line) !important; }

.topbar {
  display:flex; align-items:center; justify-content:space-between; gap:1rem;
  min-height:39px; padding:0.04rem 0.25rem 0.34rem; border-bottom:1px solid var(--line);
}
.brand-line { display:flex; align-items:center; gap:0.8rem; min-width:0; }
.brand { font-size:1.18rem; font-weight:740; letter-spacing:-0.025em; color:var(--pine); white-space:nowrap; }
.brand-divider { width:1px; height:22px; background:var(--line); }
.brand-subtitle { color:var(--muted); font-size:0.9rem; white-space:nowrap; }
.top-status { display:flex; align-items:center; gap:1.2rem; color:var(--muted); font-size:0.78rem; }
.local-label { color:var(--pine); font-weight:700; letter-spacing:0.06em; }
.synthetic-badge { display:inline-block; border:1px solid #b4d3ca; background:#e9f4f0; color:#25594f; border-radius:3px; padding:2px 7px; font-size:0.72rem; font-weight:650; }

.file-strip { min-height:54px; display:flex; align-items:center; gap:0.65rem; padding:0.2rem 0.45rem 0.45rem; border-bottom:1px solid var(--line); }
.file-chip { min-width:0; flex:1; display:flex; align-items:center; gap:0.4rem; padding:0.22rem 0.45rem; border:1px solid var(--line); border-radius:4px; background:#fbfcfc; }
.file-label { color:var(--muted); font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.055em; white-space:nowrap; }
.file-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink); font-size:0.82rem; }
.file-count { color:var(--muted); font-size:0.72rem; white-space:nowrap; }
.strip-separator { color:#a0acad; font-size:0.78rem; }

.section-label { color:var(--muted); font-size:0.69rem; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; margin:0 0 0.35rem; }
.panel-title { color:var(--ink); font-size:1.03rem; line-height:1.25; font-weight:720; margin:0; }
.panel-subtitle { color:var(--muted); font-size:0.77rem; margin-top:0.15rem; }
.queue-head { border-bottom:1px solid var(--line); padding:0.2rem 0 0.52rem; margin-bottom:0.35rem; }
.queue-counts { display:flex; gap:0.3rem; flex-wrap:wrap; color:var(--muted); font-size:0.7rem; margin-top:0.3rem; }
.count-pill { padding:0.13rem 0.38rem; border:1px solid var(--line); border-radius:3px; background:#fff; }
.count-error { color:var(--red); background:var(--red-soft); border-color:#efd4d1; }
.count-warning { color:var(--amber); background:var(--amber-soft); border-color:#eee0b6; }
.finding-title { color:var(--ink); font-family:var(--r-lead-title-family); font-size:var(--r-lead-title-font); line-height:1.14; font-weight:var(--r-lead-title-weight); letter-spacing:-0.02em; margin:0; }
.status-pill { display:inline-flex; align-items:center; gap:0.35rem; border-radius:4px; padding:0.25rem 0.52rem; font-size:0.72rem; font-weight:700; white-space:nowrap; }
.status-error { color:var(--red); background:var(--red-soft); border:1px solid #f0d4d1; }
.status-warning { color:var(--amber); background:var(--amber-soft); border:1px solid #efdfad; }
.status-info { color:var(--blue); background:var(--blue-soft); border:1px solid #d0e1ea; }
.status-pass { color:#24604d; background:#eaf4ee; border:1px solid #c9dfd1; }
.case-panel { border:1px solid var(--line); background:var(--panel); border-radius:5px; overflow:hidden; }
.case-panel-head { min-height:34px; background:#edf2f1; border-bottom:1px solid var(--line); padding:0.42rem 0.65rem; display:flex; align-items:center; justify-content:space-between; gap:0.5rem; color:var(--ink); font-size:0.81rem; font-weight:700; }
.case-panel-head small { color:var(--muted); font-size:0.72rem; font-weight:500; }
.case-banner { min-height:42px; display:flex; flex-direction:column; justify-content:center; padding:0.28rem 0.65rem; }
.case-banner-row { display:flex; align-items:center; gap:0.55rem; min-width:0; }
.case-banner-row .finding-title { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:1.1rem; }
.case-banner-message { color:var(--muted); font-size:0.7rem; line-height:1.25; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:0.08rem; }
.case-position { color:var(--muted); font-variant-numeric:tabular-nums; font-size:0.72rem; margin-left:auto; white-space:nowrap; }
.record-table-wrap { max-height:300px; overflow:auto; }
.record-table { width:100%; border-collapse:collapse; font-size:0.75rem; line-height:1.25; }
.record-table th, .record-table td { border-bottom:1px solid #e8edec; padding:0.28rem 0.5rem; text-align:left; vertical-align:top; }
.record-table th { width:42%; color:#53636a; font-weight:500; }
.record-table td { color:var(--ink); overflow-wrap:anywhere; }
.record-table tr:last-child th, .record-table tr:last-child td { border-bottom:0; }
.record-table tr.highlight { background:var(--amber-soft); }
.record-table tr.highlight th, .record-table tr.highlight td { color:#533f11; font-weight:700; }
.record-empty { padding:1.25rem 0.7rem; color:var(--muted); font-size:0.78rem; }
.inline-facts { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:0; padding:0.35rem 0.2rem 0.52rem; border-bottom:1px solid var(--line); }
.fact { padding:0.22rem 0.55rem; border-right:1px solid var(--line); min-width:0; }
.fact:last-child { border-right:0; }
.fact-label { color:var(--muted); font-size:0.7rem; margin-bottom:0.18rem; }
.fact-value { color:var(--ink); font-variant-numeric:tabular-nums; font-size:0.86rem; font-weight:670; overflow-wrap:anywhere; }
.mapping-box, .audit-box, .summary-box { border:1px solid var(--line); background:var(--panel); border-radius:5px; overflow:hidden; }
.subhead { background:#edf2f1; padding:0.35rem 0.62rem; color:var(--ink); font-weight:700; font-size:0.79rem; border-bottom:1px solid var(--line); }
.mapping-grid { display:grid; grid-template-columns:0.7fr 1.5fr; gap:0.16rem 0.75rem; padding:0.45rem 0.65rem; font-size:0.74rem; }
.mapping-key { color:var(--muted); }
.mapping-value { color:var(--ink); overflow-wrap:anywhere; }
.audit-table { width:100%; border-collapse:collapse; font-size:0.71rem; }
.audit-table th, .audit-table td { padding:0.28rem 0.5rem; border-bottom:1px solid #e8edec; text-align:left; vertical-align:top; }
.audit-table th { color:#54646b; background:#f8faf9; font-weight:650; }
.audit-table td { color:var(--ink); }
.summary-title { padding:0.32rem 0.62rem; font-size:0.75rem; font-weight:700; color:var(--ink); border-bottom:1px solid #e8edec; }
.summary-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); }
.summary-cell { padding:0.38rem 0.55rem 0.44rem; border-right:1px solid var(--line); min-width:0; }
.summary-cell:last-child { border:0; }
.summary-label { color:var(--muted); font-size:0.67rem; line-height:1.2; min-height:1.45em; }
.summary-value { color:var(--ink); font-size:0.86rem; font-weight:700; font-variant-numeric:tabular-nums; margin-top:0.15rem; overflow-wrap:anywhere; }
.summary-value.negative { color:var(--red); }
.empty-state { padding:1.1rem 0.8rem; border:1px dashed #b8c7c3; border-radius:5px; background:#f9fbfa; color:var(--muted); font-size:0.82rem; }
.privacy-note { padding:0.45rem 0.6rem; border:1px solid #e7d9b1; background:#fff8e5; border-radius:4px; color:#614b15; font-size:0.74rem; }
.small-muted { color:var(--muted); font-size:0.72rem; }

button[kind="primary"] { background:var(--pine); border-color:var(--pine); }
button[kind="primary"]:hover { background:#215f56; border-color:#215f56; }
button[kind="secondary"] { border-color:#cbd7d4; color:var(--ink); background:#fff; }
[class*="st-key-finding-row-"] button[kind="primary"] { color:var(--pine); background:var(--teal-soft); border-color:#b6d6ce; box-shadow:inset 3px 0 0 var(--teal); }
[class*="st-key-finding-row-"] button[kind="primary"]:hover { color:var(--pine); background:#d8ebe6; border-color:#a8ccc2; }
[class*="st-key-finding-row-"] button { min-height:2.15rem; padding:0.25rem 0.48rem; font-size:0.76rem; line-height:1.25; }
.st-key-run-comparison button { min-height:2.1rem; padding:0.25rem 0.55rem; font-size:0.8rem; }
.st-key-finding-controls [data-testid="stHorizontalBlock"] { align-items:center; }
.mobile-queue-link { display:none; }
.mobile-case-link { display:none; }
.summary-spacer { height:42px; }
@media (min-width: 1051px) and (min-height: 900px) {
  .summary-spacer { height:154px; }
}
button:focus-visible, input:focus-visible, [role="radio"]:focus-visible, [role="combobox"]:focus-visible { outline:3px solid #397e75 !important; outline-offset:2px; }
[data-testid="stRadio"] > div { gap:0.18rem; }
[data-testid="stRadio"] label { border-radius:3px; }
[data-testid="stDataFrame"] { border:1px solid var(--line); }
::selection { background:#cde7df; color:#183e39; }

@media (max-width: 1050px) {
  .top-status { gap:0.45rem; }
  .brand-subtitle { display:none; }
  .inline-facts { grid-template-columns:repeat(3,minmax(0,1fr)); }
  .summary-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
}
@media (max-width: 760px) {
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
  [data-testid="stColumn"] { min-width:100% !important; flex:1 1 100% !important; }
  .stHorizontalBlock:has(.st-key-review-detail) > [data-testid="stColumn"]:nth-child(2) { order:3; }
  .stHorizontalBlock:has(.st-key-review-detail) > [data-testid="stColumn"]:nth-child(3) { order:2; }
  .st-key-finding-controls [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; }
  .st-key-finding-controls [data-testid="stColumn"] { min-width:0 !important; flex:1 1 auto !important; }
  .st-key-finding-controls [data-testid="stColumn"]:first-child,
  .st-key-finding-controls [data-testid="stColumn"]:last-child { flex:0 0 4rem !important; }
  .st-key-finding-controls button { min-height:2.1rem; padding:0.18rem 0.3rem; font-size:0.75rem; }
  .case-banner-row { flex-wrap:wrap; }
  .case-banner-row .finding-title { white-space:normal; }
  .case-banner-message { white-space:normal; }
  .mobile-queue-link { display:block; margin:0.2rem 0 0.35rem; font-size:0.76rem; line-height:1.3; }
  .mobile-queue-link a { color:var(--teal); font-weight:700; text-decoration:none; }
  .mobile-queue-link a:focus-visible { outline:3px solid #397e75; outline-offset:2px; }
  .mobile-case-link { display:block; margin:0.2rem 0 0.35rem; font-size:0.76rem; line-height:1.3; }
  .mobile-case-link a { color:var(--teal); font-weight:700; text-decoration:none; }
  .mobile-case-link a:focus-visible { outline:3px solid #397e75; outline-offset:2px; }
  .summary-spacer { display:none; }
  [data-testid="stMainBlockContainer"] { padding:0.45rem 0.55rem 0.8rem !important; }
  .topbar { align-items:flex-start; }
  .top-status { flex-direction:column; align-items:flex-end; font-size:0.7rem; }
  .file-strip { align-items:stretch; flex-direction:column; }
  .inline-facts, .summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
</style>
"""


def initialize_state() -> None:
    defaults: dict[str, Any] = {
        "dataset_mode": "Bundled synthetic example",
        "active_page": "Review",
        "privacy_reveal": True,
        "include_inputs_in_export": False,
        "source_bytes": None,
        "target_bytes": None,
        "source_name": SAMPLE_SOURCE.name,
        "target_name": SAMPLE_TARGET.name,
        "mapping_payload": json.loads(SAMPLE_CONFIG.read_text(encoding="utf-8")),
        "comparison_report": None,
        "loaded_config": None,
        "source_records": {},
        "target_records": {},
        "source_columns": [],
        "target_columns": [],
        "audit_events": [],
        "selected_finding_index": 0,
        "finding_user_selected": False,
        "run_signature": None,
        "last_run": None,
        "mapping_signature": None,
        "demo_autorun_done": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def safe_filename(name: str, fallback: str) -> str:
    # Normalize both separator styles so Windows client paths cannot turn into
    # nested or traversal paths when this app runs on a POSIX host.
    clean = str(name).replace("\x00", "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    clean = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "_", clean).strip(" .")
    if not clean:
        clean = fallback
    if not clean.casefold().endswith(".csv"):
        clean += ".csv"
    stem = clean[:-4]
    if stem.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}:
        clean = f"_{clean}"
    if len(clean) > 120:
        clean = f"{clean[:-4][:116]}{clean[-4:]}"
    return clean


def decode_csv(payload: bytes, filename: str) -> tuple[list[str], dict[int, dict[str, str]]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataError(f"{filename} is not UTF-8 CSV. Export it as UTF-8 and try again.") from exc
    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        headers = next(reader, None)
        if not headers:
            raise DataError(f"{filename} is empty or has no header row.")
        records: dict[int, dict[str, str]] = {}
        record_number = 1
        for values in reader:
            if not values:
                continue
            record_number += 1
            if len(values) != len(headers):
                raise DataError(f"{filename} has an invalid row width at CSV line {reader.line_num}.")
            records[record_number] = dict(zip(headers, values))
        return headers, records
    except csv.Error as exc:
        raise DataError(f"{filename} could not be read as CSV: {exc}") from exc


def rows_for_display(records: dict[int, dict[str, str]]) -> list[dict[str, Any]]:
    return [{"row_number": number, "values": values} for number, values in records.items()]


def frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return frame.fillna("").to_dict(orient="records")


def build_mapping_payload(
    key_frame: pd.DataFrame,
    field_frame: pd.DataFrame,
    aggregate_frame: pd.DataFrame,
) -> dict[str, Any]:
    keys: list[dict[str, Any]] = []
    for row in frame_records(key_frame):
        source = str(row.get("source", "")).strip()
        target = str(row.get("target", "")).strip()
        if not source and not target:
            continue
        if not source or not target:
            raise ValueError("Each key mapping needs both a source and target column.")
        keys.append({
            "source": source,
            "target": target,
            "trim": bool(row.get("trim", True)),
            "case_insensitive": bool(row.get("case_insensitive", False)),
        })

    fields: list[dict[str, Any]] = []
    for row in frame_records(field_frame):
        source = str(row.get("source", "")).strip()
        target = str(row.get("target", "")).strip()
        kind = str(row.get("type", "string") or "string").strip()
        if not source and not target:
            continue
        if not source or not target:
            raise ValueError("Each field mapping needs both a source and target column.")
        item: dict[str, Any] = {
            "source": source,
            "target": target,
            "type": kind,
            "allow_nulls": bool(row.get("allow_nulls", True)),
        }
        if kind == "decimal":
            item["tolerance"] = str(row.get("tolerance", "0") or "0").strip()
        elif kind == "date":
            item["source_formats"] = [part.strip() for part in str(row.get("source_formats", "%Y-%m-%d")).split("|") if part.strip()]
            item["target_formats"] = [part.strip() for part in str(row.get("target_formats", "%Y-%m-%d")).split("|") if part.strip()]
        else:
            item["trim"] = bool(row.get("trim", True))
            item["case_insensitive"] = bool(row.get("case_insensitive", False))
        fields.append(item)

    aggregates: list[dict[str, Any]] = []
    for row in frame_records(aggregate_frame):
        name = str(row.get("name", "")).strip()
        source = str(row.get("source", "")).strip()
        target = str(row.get("target", "")).strip()
        tolerance = str(row.get("tolerance", "0") or "0").strip()
        if not name and not source and not target:
            continue
        if not name or not source or not target:
            raise ValueError("Each aggregate check needs a name, source column, and target column.")
        aggregates.append({"name": name, "source": source, "target": target, "tolerance": tolerance})

    if not keys:
        raise ValueError("Add at least one key mapping so rows can be matched safely.")
    if not fields:
        raise ValueError("Add at least one field rule to compare.")
    return {
        "keys": keys,
        "fields": fields,
        "aggregates": aggregates,
        "null_tokens": ["", "null", "none", "n/a"],
        "unmatched_source_severity": "error",
        "unmatched_target_severity": "error",
        "duplicate_severity": "error",
        "max_findings": 1000,
    }


def default_editor_frames(payload: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    keys = pd.DataFrame([
        {
            "source": item.get("source", ""),
            "target": item.get("target", ""),
            "trim": item.get("trim", True),
            "case_insensitive": item.get("case_insensitive", False),
        }
        for item in payload.get("keys", [])
    ], columns=["source", "target", "trim", "case_insensitive"])
    fields = pd.DataFrame([
        {
            "source": item.get("source", ""),
            "target": item.get("target", ""),
            "type": item.get("type", "string"),
            "tolerance": item.get("tolerance", "0"),
            "source_formats": " | ".join(item.get("source_formats", ["%Y-%m-%d"])),
            "target_formats": " | ".join(item.get("target_formats", ["%Y-%m-%d"])),
            "trim": item.get("trim", True),
            "case_insensitive": item.get("case_insensitive", False),
            "allow_nulls": item.get("allow_nulls", True),
        }
        for item in payload.get("fields", [])
    ], columns=["source", "target", "type", "tolerance", "source_formats", "target_formats", "trim", "case_insensitive", "allow_nulls"])
    aggregates = pd.DataFrame([
        {"name": item.get("name", ""), "source": item.get("source", ""), "target": item.get("target", ""), "tolerance": item.get("tolerance", "0")}
        for item in payload.get("aggregates", [])
    ], columns=["name", "source", "target", "tolerance"])
    if keys.empty:
        keys.loc[0] = ["", "", True, False]
    if fields.empty:
        fields.loc[0] = ["", "", "string", "0", "%Y-%m-%d", "%Y-%m-%d", True, False, True]
    if aggregates.empty:
        aggregates.loc[0] = ["", "", "", "0"]
    return keys, fields, aggregates


def file_signature(source_bytes: bytes, target_bytes: bytes, source_name: str, target_name: str) -> str:
    digest = hashlib.sha256()
    digest.update(source_name.encode("utf-8", "replace"))
    digest.update(b"\0")
    digest.update(source_bytes)
    digest.update(b"\0")
    digest.update(target_name.encode("utf-8", "replace"))
    digest.update(b"\0")
    digest.update(target_bytes)
    return digest.hexdigest()


def comparison_signature(
    source_bytes: bytes,
    target_bytes: bytes,
    source_name: str,
    target_name: str,
    mapping_payload: dict[str, Any],
) -> str:
    digest = hashlib.sha256()
    digest.update(file_signature(source_bytes, target_bytes, source_name, target_name).encode("ascii"))
    digest.update(b"\0")
    digest.update(json.dumps(mapping_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


def clear_comparison_state() -> None:
    st.session_state.comparison_report = None
    st.session_state.comparison_error = None
    st.session_state.source_records = {}
    st.session_state.target_records = {}
    st.session_state.loaded_config = None
    st.session_state.run_signature = None
    st.session_state.last_run = None
    st.session_state.selected_finding_index = 0
    st.session_state.finding_user_selected = False
    st.session_state.pop("finding_select_index", None)


def run_comparison(
    source_bytes: bytes,
    target_bytes: bytes,
    source_name: str,
    target_name: str,
    mapping_payload: dict[str, Any],
) -> tuple[ComparisonReport, dict[int, dict[str, str]], dict[int, dict[str, str]], Any]:
    with tempfile.TemporaryDirectory(prefix="migration-workbench-") as temp_dir:
        temp_path = Path(temp_dir)
        # Keep the side in the staging path: source and target exports commonly
        # share a basename such as export.csv, and must never overwrite each other.
        source_path = temp_path / "source" / safe_filename(source_name, "source.csv")
        target_path = temp_path / "target" / safe_filename(target_name, "target.csv")
        config_path = temp_path / "mapping.json"
        source_path.parent.mkdir()
        target_path.parent.mkdir()
        source_path.write_bytes(source_bytes)
        target_path.write_bytes(target_bytes)
        config_path.write_text(json.dumps(mapping_payload, indent=2), encoding="utf-8")
        config = load_config(config_path)
        report = compare_files(source_path, target_path, config, include_values=True)
    source_columns, source_records = decode_csv(source_bytes, source_name)
    target_columns, target_records = decode_csv(target_bytes, target_name)
    return report, source_records, target_records, (config, source_columns, target_columns)


def active_files() -> tuple[bytes | None, bytes | None, str, str]:
    if st.session_state.dataset_mode == "Bundled synthetic example":
        return SAMPLE_SOURCE.read_bytes(), SAMPLE_TARGET.read_bytes(), SAMPLE_SOURCE.name, SAMPLE_TARGET.name
    return (
        st.session_state.source_bytes,
        st.session_state.target_bytes,
        st.session_state.source_name if st.session_state.source_bytes is not None else "No source selected",
        st.session_state.target_name if st.session_state.target_bytes is not None else "No target selected",
    )


def display_header(source_name: str, target_name: str, source_bytes: bytes | None, target_bytes: bytes | None) -> bool:
    def record_count(payload: bytes | None, filename: str) -> str:
        if payload is None:
            return "not selected"
        try:
            _, records = decode_csv(payload, filename)
            return f"{len(records):,} records"
        except DataError:
            return "CSV not read"

    badge = "SYNTHETIC EXAMPLE" if st.session_state.dataset_mode == "Bundled synthetic example" else "LOCAL FILES"
    st.markdown(
        f"""
        <div class="topbar">
          <div class="brand-line">
            <span class="brand">Migration Workbench</span>
            <span class="brand-divider"></span>
            <span class="brand-subtitle">Invoice data migration review</span>
          </div>
          <div class="top-status">
            <span><span class="local-label">LOCAL</span><br>Session only</span>
            <span class="synthetic-badge">{badge}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    source_count = record_count(source_bytes, source_name)
    target_count = record_count(target_bytes, target_name)
    nav_space, queue_space, content = st.columns([0.11, 0.20, 0.69], gap="small", vertical_alignment="center")
    with content:
        source_col, target_col, action_col = st.columns([0.39, 0.39, 0.22], gap="small", vertical_alignment="center")
        with source_col:
            st.markdown(f'<div class="file-chip"><span class="file-label">Source</span><span class="file-name">{html.escape(source_name)}</span><span class="file-count">{html.escape(source_count)}</span></div>', unsafe_allow_html=True)
        with target_col:
            st.markdown(f'<div class="file-chip"><span class="file-label">Target</span><span class="file-name">{html.escape(target_name)}</span><span class="file-count">{html.escape(target_count)}</span></div>', unsafe_allow_html=True)
        with action_col:
            return st.button(
                "Run comparison",
                type="primary",
                icon=":material/play_arrow:",
                width="stretch",
                disabled=source_bytes is None or target_bytes is None,
                key="run-comparison",
            )
    return False


def finding_identifier(index: int, finding: Finding) -> str:
    return f"{index}:{finding.code}:{','.join(map(str, finding.source_rows))}:{','.join(map(str, finding.target_rows))}"


def preferred_finding_index(report: ComparisonReport) -> int:
    """Open a useful paired field exception first when the user has not chosen one."""
    for code in ("decimal_mismatch", "field_mismatch", "date_mismatch"):
        for index, finding in enumerate(report.findings):
            if finding.code == code and finding.source_rows and finding.target_rows:
                return index
    for index, finding in enumerate(report.findings):
        if finding.source_rows and finding.target_rows:
            return index
    return 0


def finding_title(finding: Finding) -> str:
    if finding.code == "decimal_mismatch":
        field_names = (finding.field or "").casefold()
        if any(name in field_names for name in ("invoice_total", "total_amount")):
            return "Invoice total differs"
        if any(name in field_names for name in ("tax_amount", "tax_total")):
            return "Tax amount differs"
        return "Amount differs" if any(word in field_names for word in ("amount", "total", "balance", "price")) else "Decimal value differs"
    titles = {
        "duplicate_source_key": "Duplicate source key",
        "duplicate_target_key": "Duplicate target key",
        "missing_target_row": "Missing target record",
        "unexpected_target_row": "Unexpected target record",
        "blank_key": "Blank key value",
        "field_mismatch": "Text field differs",
        "date_mismatch": "Date differs",
        "invalid_source_decimal": "Invalid source amount",
        "invalid_target_decimal": "Invalid target amount",
        "invalid_source_date": "Invalid source date",
        "invalid_target_date": "Invalid target date",
        "null_value_not_allowed": "Required value is blank",
        "aggregate_mismatch": "Control total differs",
        "findings_truncated": "Finding limit reached",
    }
    return titles.get(finding.code, finding.code.replace("_", " ").capitalize())


def finding_label(index: int, finding: Finding) -> str:
    severity = "ERR" if finding.severity == "error" else "WARN"
    refs: list[str] = []
    if finding.source_rows:
        refs.extend(f"S{row}" for row in finding.source_rows)
    if finding.target_rows:
        refs.extend(f"T{row}" for row in finding.target_rows)
    reference = " / ".join(refs) or "aggregate"
    return f"{severity}  {reference}  ·  {finding_title(finding)}"


def current_rule(finding: Finding, config: Any) -> tuple[str, str, str, str]:
    if finding.field and " -> " in finding.field:
        source, target = finding.field.split(" -> ", 1)
        for rule in config.fields:
            if rule.source == source and rule.target == target:
                return source, target, rule.kind, str(rule.tolerance)
        for rule in config.aggregates:
            if rule.source == source and rule.target == target:
                return source, target, "aggregate", str(rule.tolerance)
    if config.keys:
        rule = config.keys[0]
        return rule.source, rule.target, "key", "—"
    return "—", "—", "—", "—"


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def record_card(
    title: str,
    filename: str,
    row_number: int | None,
    values: dict[str, str] | None,
    columns: list[str],
    reveal: bool,
    highlight_fields: set[str],
) -> str:
    side = "S" if title.casefold().startswith("source") else "T"
    row_ref = f"{side}{row_number}" if row_number is not None else "No unique match"
    head = f'<div class="case-panel-head"><span>{escape(title)} <small>({escape(filename)} · {escape(row_ref)})</small></span></div>'
    if values is None:
        return f'<div class="case-panel">{head}<div class="record-empty">No unique record on this side for the selected finding.</div></div>'
    shown_columns = columns[:MAX_VISIBLE_RECORD_FIELDS]
    rows: list[str] = []
    for column in shown_columns:
        raw_value = values.get(column, "")
        value = raw_value if reveal else "Hidden"
        cls = " class=\"highlight\"" if column in highlight_fields else ""
        rows.append(f"<tr{cls}><th>{escape(column)}</th><td>{escape(value) or '&nbsp;'}</td></tr>")
    if not rows:
        rows.append('<tr><td colspan="2">No columns found.</td></tr>')
    remainder = ""
    if len(columns) > len(shown_columns):
        remainder = f'<div class="small-muted" style="padding:0.2rem 0.5rem">Showing {len(shown_columns)} of {len(columns)} columns.</div>'
    table = f'<div class="record-table-wrap"><table class="record-table" aria-label="{escape(title)}"><tbody>{"".join(rows)}</tbody></table></div>{remainder}'
    return f'<div class="case-panel">{head}{table}</div>'


def value_for_summary(
    record: dict[int, dict[str, str]], row_number: int | None, column: str, reveal: bool
) -> str:
    if row_number is None:
        return "—"
    row = record.get(row_number)
    if row is None:
        return "—"
    value = row.get(column, "")
    return value if reveal and value else ("Hidden" if value else "—")


def make_audit_pack(
    report: ComparisonReport,
    mapping_payload: dict[str, Any],
    source_bytes: bytes,
    target_bytes: bytes,
    source_name: str,
    target_name: str,
    include_inputs: bool,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("comparison.json", json_report(report, include_values=False))
        archive.writestr("comparison.md", markdown_report(report, include_values=False))
        archive.writestr("mapping.json", json.dumps(mapping_payload, indent=2, ensure_ascii=False) + "\n")
        rows = io.StringIO(newline="")
        writer = csv.writer(rows)
        writer.writerow(["severity", "code", "field", "source_rows", "target_rows", "message"])
        for finding in report.findings:
            writer.writerow([csv_safe_cell(value) for value in [
                finding.severity,
                finding.code,
                finding.field or "",
                ";".join(map(str, finding.source_rows)),
                ";".join(map(str, finding.target_rows)),
                finding.message,
            ]])
        archive.writestr("findings.csv", rows.getvalue())
        input_state = "included" if include_inputs else "not included (default for privacy)"
        safe_source_name = safe_filename(source_name, "source.csv")
        safe_target_name = safe_filename(target_name, "target.csv")
        readme = f"""Migration Workbench audit pack

Comparison status: {report.status}
Source extract: {safe_source_name} ({report.source_row_count} rows)
Target extract: {safe_target_name} ({report.target_row_count} rows)
Input extracts: {input_state}

The JSON and Markdown reports redact raw field values. The mapping file records the configured checks. Included inputs are stored separately under inputs/source/ and inputs/target/ so equal filenames do not collide. To reproduce the comparison, install this project with its UI extra and provide the same two CSV extracts, or run the CLI with mapping.json. A passing result confirms only the configured CSV-level checks; it does not certify business policy or production cutover readiness.
"""
        archive.writestr("README.txt", readme)
        if include_inputs:
            archive.writestr(f"inputs/source/{safe_source_name}", source_bytes)
            archive.writestr(f"inputs/target/{safe_target_name}", target_bytes)
    return buffer.getvalue()


def csv_safe_cell(value: Any) -> str:
    text = str(value)
    leading = text.lstrip(" \t\r\n")
    if text.startswith(("\t", "\r", "\n")) or leading.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def log_event(label: str, detail: str) -> None:
    events = list(st.session_state.get("audit_events", []))
    events.insert(0, {
        "time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "event": label,
        "detail": detail,
    })
    st.session_state.audit_events = events[:12]


def run_and_store(source_bytes: bytes, target_bytes: bytes, source_name: str, target_name: str, mapping: dict[str, Any]) -> None:
    try:
        report, source_records, target_records, loaded = run_comparison(
            source_bytes, target_bytes, source_name, target_name, mapping
        )
    except (ConfigError, DataError, ValueError, OSError, InvalidOperation) as exc:
        clear_comparison_state()
        st.session_state.comparison_error = str(exc)
        return
    st.session_state.comparison_error = None
    st.session_state.comparison_report = report
    st.session_state.source_records = source_records
    st.session_state.target_records = target_records
    config, source_columns, target_columns = loaded
    st.session_state.source_columns = source_columns
    st.session_state.target_columns = target_columns
    st.session_state.loaded_config = config
    st.session_state.source_name = source_name
    st.session_state.target_name = target_name
    st.session_state.run_signature = comparison_signature(
        source_bytes, target_bytes, source_name, target_name, mapping
    )
    st.session_state.last_run = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    st.session_state.selected_finding_index = preferred_finding_index(report)
    st.session_state.finding_user_selected = False
    st.session_state.pop("finding_select_index", None)
    log_event("Comparison run", f"{source_name} → {target_name} · {report.status}")


def render_mapping_editors(source_columns: list[str], target_columns: list[str]) -> None:
    signature = (tuple(source_columns), tuple(target_columns), st.session_state.dataset_mode)
    if signature != st.session_state.mapping_signature:
        editor_keys = ["keys-editor", "fields-editor", "aggregates-editor"]
        for key in editor_keys:
            st.session_state.pop(key, None)
        if st.session_state.dataset_mode == "Bundled synthetic example":
            initial = json.loads(SAMPLE_CONFIG.read_text(encoding="utf-8"))
        else:
            initial = {"keys": [], "fields": [], "aggregates": []}
        key_frame, field_frame, aggregate_frame = default_editor_frames(initial)
        st.session_state.keys_editor_data = key_frame
        st.session_state.fields_editor_data = field_frame
        st.session_state.aggregates_editor_data = aggregate_frame
        if st.session_state.dataset_mode != "Bundled synthetic example":
            st.session_state.mapping_payload = {
                "keys": [],
                "fields": [],
                "aggregates": [],
                "null_tokens": ["", "null", "none", "n/a"],
                "unmatched_source_severity": "error",
                "unmatched_target_severity": "error",
                "duplicate_severity": "error",
                "max_findings": 1000,
            }
        else:
            st.session_state.mapping_payload = initial
        st.session_state.mapping_signature = signature

    source_options = ["", *source_columns]
    target_options = ["", *target_columns]

    st.markdown("#### Record identity")
    st.caption("Choose the columns that identify the same business record on both sides.")
    key_frame = st.data_editor(
        st.session_state.keys_editor_data,
        key="keys-editor",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "source": st.column_config.SelectboxColumn("Source key", options=source_options, required=False),
            "target": st.column_config.SelectboxColumn("Target key", options=target_options, required=False),
            "trim": st.column_config.CheckboxColumn("Trim", default=True),
            "case_insensitive": st.column_config.CheckboxColumn("Ignore case", default=False),
        },
    )

    st.markdown("#### Field comparison rules")
    st.caption("Map each value explicitly. Decimal tolerances use absolute units in the source currency.")
    field_frame = st.data_editor(
        st.session_state.fields_editor_data,
        key="fields-editor",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "source": st.column_config.SelectboxColumn("Source field", options=source_options, required=False),
            "target": st.column_config.SelectboxColumn("Target field", options=target_options, required=False),
            "type": st.column_config.SelectboxColumn("Type", options=["string", "decimal", "date"], required=True),
            "tolerance": st.column_config.TextColumn("Tolerance", help="Used for decimal fields."),
            "source_formats": st.column_config.TextColumn("Source date formats", help="Use | between Python strptime formats."),
            "target_formats": st.column_config.TextColumn("Target date formats", help="Use | between Python strptime formats."),
            "trim": st.column_config.CheckboxColumn("Trim", default=True),
            "case_insensitive": st.column_config.CheckboxColumn("Ignore case", default=False),
            "allow_nulls": st.column_config.CheckboxColumn("Allow nulls", default=True),
        },
    )

    st.markdown("#### Aggregate controls")
    st.caption("Optional decimal totals help catch value drift across the full extracts.")
    aggregate_frame = st.data_editor(
        st.session_state.aggregates_editor_data,
        key="aggregates-editor",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "name": st.column_config.TextColumn("Check name"),
            "source": st.column_config.SelectboxColumn("Source total field", options=source_options, required=False),
            "target": st.column_config.SelectboxColumn("Target total field", options=target_options, required=False),
            "tolerance": st.column_config.TextColumn("Tolerance"),
        },
    )

    if st.button("Save mapping rules", type="secondary", icon=":material/save:", key="save-mapping"):
        try:
            mapping = build_mapping_payload(key_frame, field_frame, aggregate_frame)
            # Validate the exact serialized mapping with the same strict loader used by the engine.
            with tempfile.TemporaryDirectory(prefix="migration-mapping-") as temp_dir:
                config_path = Path(temp_dir) / "mapping.json"
                config_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
                load_config(config_path)
            st.session_state.mapping_payload = mapping
            st.session_state.keys_editor_data = key_frame
            st.session_state.fields_editor_data = field_frame
            st.session_state.aggregates_editor_data = aggregate_frame
            clear_comparison_state()
            st.success("Mapping rules saved. Run a new comparison to refresh results.")
        except (ConfigError, ValueError) as exc:
            st.error(str(exc))


def render_setup_page(source_bytes: bytes | None, target_bytes: bytes | None, source_name: str, target_name: str) -> None:
    st.markdown("## File setup")
    st.markdown("Choose one bundled synthetic comparison or load a pair of local UTF-8 CSV extracts.")
    st.radio(
        "Dataset",
        ["Bundled synthetic example", "Upload CSV pair"],
        horizontal=True,
        key="dataset_mode",
        on_change=dataset_mode_changed,
    )
    if st.session_state.dataset_mode == "Upload CSV pair":
        st.markdown("<div class='privacy-note'>Uploaded extracts stay in this app session and are written to short-lived temporary files only while a comparison runs. When hosted remotely, the host processes the files.</div>", unsafe_allow_html=True)
        left, right = st.columns(2)
        upload_changed = False
        with left:
            source_upload = st.file_uploader("Source extract", type=["csv"], key="source-upload", max_upload_size=MAX_UPLOAD_MB)
            if source_upload is not None:
                new_bytes = source_upload.getvalue()
                new_name = safe_filename(source_upload.name, "source.csv")
                if new_bytes != st.session_state.source_bytes or new_name != st.session_state.source_name:
                    st.session_state.source_bytes = new_bytes
                    st.session_state.source_name = new_name
                    upload_changed = True
        with right:
            target_upload = st.file_uploader("Target extract", type=["csv"], key="target-upload", max_upload_size=MAX_UPLOAD_MB)
            if target_upload is not None:
                new_bytes = target_upload.getvalue()
                new_name = safe_filename(target_upload.name, "target.csv")
                if new_bytes != st.session_state.target_bytes or new_name != st.session_state.target_name:
                    st.session_state.target_bytes = new_bytes
                    st.session_state.target_name = new_name
                    upload_changed = True
        if upload_changed:
            clear_comparison_state()
            st.session_state.mapping_signature = None
            st.rerun()
        if st.session_state.source_bytes is None or st.session_state.target_bytes is None:
            st.info("Add both CSV files to continue. Each file is limited to 25 MB.")
            return
        source_bytes, target_bytes, source_name, target_name = active_files()
    else:
        source_bytes, target_bytes, source_name, target_name = active_files()

    try:
        source_columns, _ = decode_csv(source_bytes, source_name) if source_bytes else ([], {})
        target_columns, _ = decode_csv(target_bytes, target_name) if target_bytes else ([], {})
    except DataError as exc:
        st.error(str(exc))
        return

    st.markdown(f"**Source columns:** {len(source_columns)} &nbsp;&nbsp; **Target columns:** {len(target_columns)}", unsafe_allow_html=True)
    render_mapping_editors(source_columns, target_columns)


def dataset_mode_changed() -> None:
    clear_comparison_state()
    st.session_state.mapping_signature = None
    st.session_state.privacy_reveal = st.session_state.dataset_mode == "Bundled synthetic example"


def render_queue(report: ComparisonReport) -> tuple[int | None, list[tuple[int, Finding]]]:
    all_items = list(enumerate(report.findings))
    error_count = sum(item.severity == "error" for _, item in all_items)
    warning_count = sum(item.severity == "warning" for _, item in all_items)
    st.markdown('<div id="exception-queue"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="queue-head">
          <div class="panel-title">Exceptions <span class="small-muted">({len(all_items)})</span></div>
          <div class="queue-counts"><span class="count-pill count-error">Errors {error_count}</span><span class="count-pill count-warning">Warnings {warning_count}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="mobile-case-link"><a href="#selected-case">Back to case ↑</a></div>', unsafe_allow_html=True)
    severity = st.radio("Filter", ["All", "Errors", "Warnings"], horizontal=True, label_visibility="collapsed", key="severity-filter")
    filtered = [(index, item) for index, item in all_items if severity == "All" or item.severity == ("error" if severity == "Errors" else "warning")]
    query = st.text_input("Search exceptions", placeholder="Search code, row, field…", label_visibility="collapsed", key="finding-search")
    if query.strip():
        q = query.strip().casefold()
        filtered = [(index, item) for index, item in filtered if q in " ".join([item.code, item.message, item.field or "", *map(str, item.source_rows), *map(str, item.target_rows)]).casefold()]
    if not filtered:
        if not all_items:
            message = "No exceptions found. All configured comparisons completed without findings."
        else:
            message = "No exceptions match this filter. Clear the search or select another severity."
        st.markdown(f'<div class="empty-state">{message}</div>', unsafe_allow_html=True)
        return None, filtered
    selected_index = st.session_state.get("selected_finding_index", filtered[0][0])
    if selected_index not in [index for index, _ in filtered]:
        selected_index = filtered[0][0]
        st.session_state.selected_finding_index = selected_index
    with st.container(height=570, border=False):
        for severity_value, group_title, prefix in (("error", "Errors", "E"), ("warning", "Warnings", "W")):
            group_items = [(index, item) for index, item in filtered if item.severity == severity_value]
            if not group_items:
                continue
            st.markdown(f'<div class="section-label">{group_title} ({len(group_items)})</div>', unsafe_allow_html=True)
            for number, (index, item) in enumerate(group_items, start=1):
                references = "/".join([*(f"S{row}" for row in item.source_rows), *(f"T{row}" for row in item.target_rows)]) or "aggregate"
                label = f"{prefix}{number:03}  {references}  ·  {finding_title(item)}"
                st.button(
                    label,
                    key=f"finding-row-{index}",
                    help=item.message,
                    type="primary" if index == selected_index else "secondary",
                    width="stretch",
                    on_click=set_selected_finding,
                    args=(index,),
                )
    return selected_index, filtered


def render_facts(finding: Finding, config: Any, source_record: dict[str, str] | None, target_record: dict[str, str] | None, reveal: bool) -> None:
    source_field, target_field, kind, tolerance = current_rule(finding, config)
    source_row = finding.source_rows[0] if finding.source_rows else None
    target_row = finding.target_rows[0] if finding.target_rows else None
    source_value = source_record.get(source_field, "") if source_record and source_field != "—" else ""
    target_value = target_record.get(target_field, "") if target_record and target_field != "—" else ""
    if finding.code == "aggregate_mismatch" and not finding.source_rows and not finding.target_rows:
        source_value = finding.source_value or ""
        target_value = finding.target_value or ""
    delta = "—"
    if reveal and kind in {"decimal", "aggregate"} and source_value and target_value:
        try:
            delta = format(abs(Decimal(source_value) - Decimal(target_value)), "f")
        except InvalidOperation:
            delta = "—"
    ref = " · ".join([*(f"S{n}" for n in finding.source_rows), *(f"T{n}" for n in finding.target_rows)]) or "Aggregate"
    values = [
        ("Row reference", ref),
        ("Mapped field", f"{source_field} → {target_field}"),
        ("Rule type", kind),
        ("Tolerance", tolerance),
        ("Source value", source_value if reveal and source_value else ("Hidden" if source_value else "—")),
        ("Target value", target_value if reveal and target_value else ("Hidden" if target_value else "—")),
    ]
    if reveal and delta != "—":
        values[-1] = ("Absolute difference", delta)
    cells = "".join(f'<div class="fact"><div class="fact-label">{escape(label)}</div><div class="fact-value">{escape(value)}</div></div>' for label, value in values)
    st.markdown(f'<div class="inline-facts">{cells}</div>', unsafe_allow_html=True)


def render_mapping_panel(finding: Finding, config: Any, show_values: bool) -> None:
    source_field, target_field, kind, tolerance = current_rule(finding, config)
    result_text = finding.message
    if show_values and (finding.source_value is not None or finding.target_value is not None):
        result_text += f" · Source {finding.source_value or '—'} → target {finding.target_value or '—'}"
    mapping_text = f"{source_field} → {target_field}"
    if kind == "key":
        result_text = "Key rule identifies the record pair; this finding has no field tolerance."
    details = [
        ("Field", source_field if kind in {"key", "—"} else source_field),
        ("Mapping rule", mapping_text),
        ("Type / tolerance", f"{kind} / {tolerance}"),
        ("Result", result_text),
    ]
    rows = "".join(f'<div class="mapping-key">{escape(label)}</div><div class="mapping-value">{escape(value)}</div>' for label, value in details)
    st.markdown(f'<div class="mapping-box"><div class="subhead">Mapping rule and tolerance</div><div class="mapping-grid">{rows}</div></div>', unsafe_allow_html=True)


def render_audit_trail() -> None:
    events = st.session_state.get("audit_events", [])[:4]
    if not events:
        body = '<tr><td colspan="3">No activity in this session yet.</td></tr>'
    else:
        body = "".join(
            f"<tr><td>{escape(event['time'])}</td><td>system</td><td>{escape(event['event'])} · {escape(event['detail'])}</td></tr>"
            for event in events
        )
    st.markdown(
        f'<div class="audit-box"><div class="subhead">Session activity <span class="small-muted">(in memory; not a durable audit log)</span></div><table class="audit-table"><thead><tr><th>Time</th><th>Actor</th><th>Event</th></tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def render_reconciliation_summary(report: ComparisonReport, reveal: bool) -> None:
    aggregate = report.aggregates[0] if len(report.aggregates) == 1 else None
    multiple_aggregates = len(report.aggregates) > 1

    def aggregate_value(value: Decimal | None) -> str:
        if multiple_aggregates:
            return "See Reconciliation" if reveal else "Hidden"
        if aggregate is None:
            return "—"
        if not reveal:
            return "Hidden"
        return format(value, "f") if value is not None else "Not evaluated"

    source_total = aggregate_value(aggregate.source_total if aggregate else None)
    target_total = aggregate_value(aggregate.target_total if aggregate else None)
    difference = aggregate_value(abs(aggregate.difference) if aggregate and aggregate.difference is not None else None)
    if aggregate:
        summary_note = f"· Control: {escape(aggregate.name)}"
    elif multiple_aggregates:
        summary_note = f"· {len(report.aggregates)} controls; see Reconciliation"
    else:
        summary_note = "· synthetic or local CSV data"
    metrics = [
        ("Source total", source_total),
        ("Target total", target_total),
        ("Difference", difference),
        ("Matched keys", f"{report.matched_key_count:,}"),
        ("Unmatched source", f"{report.unmatched_source_count:,}"),
        ("Unmatched target", f"{report.unmatched_target_count:,}"),
    ]
    cells = "".join(
        f'<div class="summary-cell"><div class="summary-label">{escape(label)}</div><div class="summary-value">{escape(value)}</div></div>'
        for label, value in metrics
    )
    st.markdown(
        f'<div class="summary-box"><div class="summary-title">Reconciliation summary <span class="small-muted">{summary_note}</span></div><div class="summary-grid">{cells}</div></div>',
        unsafe_allow_html=True,
    )


def render_review_page(
    report: ComparisonReport | None,
    source_bytes: bytes | None,
    target_bytes: bytes | None,
    source_name: str,
    target_name: str,
) -> None:
    review_layout = st.session_state.get("active_page", "Review") == "Review"
    if review_layout:
        nav_col, queue_col, detail_col = st.columns([0.11, 0.20, 0.69], gap="small")
    else:
        nav_col, detail_col = st.columns([0.15, 0.85], gap="small")
        queue_col = None
    with nav_col:
        st.markdown('<div class="section-label">Workspace</div>', unsafe_allow_html=True)
        page = st.radio(
            "Workspace navigation",
            ["Review", "File setup", "Reconciliation", "Export"],
            key="active_page",
            label_visibility="collapsed",
        )
        if page == "Review":
            st.markdown('<div class="small-muted">Local CSV review</div>', unsafe_allow_html=True)

    if page == "File setup":
        with detail_col:
            render_setup_page(source_bytes, target_bytes, source_name, target_name)
        return
    if page == "Reconciliation":
        with detail_col:
            render_reconciliation_page(report)
        return
    if page == "Export":
        with detail_col:
            render_export_page(report, source_bytes, target_bytes, source_name, target_name)
        return

    assert queue_col is not None
    if report is not None and report.findings and not st.session_state.get("finding_user_selected", False):
        st.session_state.selected_finding_index = preferred_finding_index(report)
    with queue_col:
        if report is None:
            st.markdown('<div class="queue-head"><div class="panel-title">Exceptions</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="empty-state">Run a comparison to populate the exception queue.</div>', unsafe_allow_html=True)
            selected_index, filtered = None, []
        else:
            selected_index, filtered = render_queue(report)

    with detail_col:
        with st.container(key="review-detail"):
            if report is None:
                st.markdown('<div class="empty-state">No comparison is ready. Open File setup to choose a CSV pair, then run the comparison.</div>', unsafe_allow_html=True)
                return

            if selected_index is None:
                status_class = "status-pass" if report.status == "PASS" else "status-warning"
                status_label = "PASS" if report.status == "PASS" else "PASS WITH WARNINGS"
                st.markdown(f'<div class="case-panel"><div class="case-panel-head"><span>No exceptions found</span><span class="status-pill {status_class}">{status_label}</span></div><div class="record-empty">All configured comparisons completed without findings. Review the mapping and populations before treating this as sign-off.</div></div>', unsafe_allow_html=True)
                render_reconciliation_summary(report, st.session_state.privacy_reveal)
                return

            finding = report.findings[selected_index]
            title = finding_title(finding)
            severity_class = "status-error" if finding.severity == "error" else "status-warning"
            severity_label = "Error" if finding.severity == "error" else "Warning"
            position = next((idx for idx, (global_idx, _) in enumerate(filtered) if global_idx == selected_index), 0)
            st.markdown('<div id="selected-case"></div>', unsafe_allow_html=True)
            with st.container(key="finding-controls"):
                previous_col, title_col, next_col = st.columns([0.15, 0.70, 0.15], gap="small", vertical_alignment="center")
                with previous_col:
                    st.button(
                        "Previous",
                        key="previous-finding",
                        help="Previous exception",
                        disabled=position == 0,
                        on_click=lambda idx=filtered[position - 1][0] if position > 0 else selected_index: set_selected_finding(idx),
                    )
                with title_col:
                    st.markdown(
                        f'<div class="case-panel case-banner"><div class="case-banner-row"><span class="finding-title">{escape(title)}</span><span class="status-pill {severity_class}">{severity_label}</span><span class="case-position">{position + 1} / {len(filtered)}</span></div><div class="case-banner-message">{escape(finding.message)}</div></div>',
                        unsafe_allow_html=True,
                    )
                with next_col:
                    st.button(
                        "Next",
                        key="next-finding",
                        help="Next exception",
                        disabled=position >= len(filtered) - 1,
                        on_click=lambda idx=filtered[position + 1][0] if position < len(filtered) - 1 else selected_index: set_selected_finding(idx),
                    )
            st.markdown('<div class="mobile-queue-link"><a href="#exception-queue">Browse exceptions ↓</a></div>', unsafe_allow_html=True)

            reveal = st.checkbox("Show source and target values", key="privacy_reveal", help="Raw values stay in this local app session and are excluded from the default audit pack.")
            if reveal and st.session_state.dataset_mode != "Bundled synthetic example":
                st.markdown('<div class="privacy-note">Raw record values are visible on this screen. Exported reports remain redacted unless you separately include the source files.</div>', unsafe_allow_html=True)

            source_row_number = finding.source_rows[0] if finding.source_rows else None
            target_row_number = finding.target_rows[0] if finding.target_rows else None
            source_record = st.session_state.source_records.get(source_row_number) if source_row_number is not None else None
            target_record = st.session_state.target_records.get(target_row_number) if target_row_number is not None else None
            config = st.session_state.get("loaded_config")
            if config is None:
                try:
                    with tempfile.TemporaryDirectory(prefix="migration-view-config-") as temp_dir:
                        config_path = Path(temp_dir) / "mapping.json"
                        config_path.write_text(json.dumps(st.session_state.mapping_payload), encoding="utf-8")
                        config = load_config(config_path)
                except (ConfigError, OSError) as exc:
                    st.error(f"Could not load the selected mapping: {exc}")
                    return

            render_facts(finding, config, source_record, target_record, reveal)
            source_cols = st.session_state.source_columns
            target_cols = st.session_state.target_columns
            src_field, tgt_field, _, _ = current_rule(finding, config)
            key_fields = {rule.source for rule in config.keys} | {rule.target for rule in config.keys}
            highlights = {src_field, tgt_field} | key_fields
            source_panel, target_panel = st.columns([1, 1], gap="small")
            with source_panel:
                st.markdown(record_card("Source record", source_name, source_row_number, source_record, source_cols, reveal, highlights), unsafe_allow_html=True)
            with target_panel:
                st.markdown(record_card("Target record", target_name, target_row_number, target_record, target_cols, reveal, highlights), unsafe_allow_html=True)
            render_mapping_panel(finding, config, reveal)
            render_audit_trail()
            if st.session_state.get("active_page", "Review") == "Review":
                st.markdown('<div class="summary-spacer"></div>', unsafe_allow_html=True)
            render_reconciliation_summary(report, reveal)


def set_selected_finding(index: int) -> None:
    st.session_state.selected_finding_index = index
    st.session_state.finding_user_selected = True
    st.session_state.finding_select_index = index
    log_event("Exception opened", f"Finding {index + 1}")


def render_reconciliation_page(report: ComparisonReport | None) -> None:
    st.markdown("## Reconciliation")
    if report is None:
        st.markdown('<div class="empty-state">Run a comparison to see aggregate and population controls.</div>', unsafe_allow_html=True)
        return
    render_reconciliation_summary(report, st.session_state.privacy_reveal)
    st.markdown("### Population controls")
    rows = [
        ("Source rows", report.source_row_count),
        ("Target rows", report.target_row_count),
        ("Matched unique keys", report.matched_key_count),
        ("Unmatched source rows", report.unmatched_source_count),
        ("Unmatched target rows", report.unmatched_target_count),
        ("Duplicate source key groups", report.duplicate_source_groups),
        ("Duplicate target key groups", report.duplicate_target_groups),
        ("Invalid key rows", report.invalid_key_row_count),
        ("Compared field cells", report.compared_field_cells),
        ("Mismatched field cells", report.mismatched_field_cells),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Control", "Result"]), hide_index=True, width="stretch")
    st.markdown("### Aggregate checks")
    if not report.aggregates:
        st.markdown('<div class="empty-state">No aggregate controls are configured.</div>', unsafe_allow_html=True)
        return
    aggregate_rows = []
    for item in report.aggregates:
        aggregate_rows.append({
            "Check": item.name,
            "Status": "Not evaluated" if item.within_tolerance is None else ("Pass" if item.within_tolerance else "Fail"),
            "Source field": item.source_field,
            "Target field": item.target_field,
            "Tolerance": str(item.tolerance),
            "Source total": str(item.source_total) if st.session_state.privacy_reveal and item.source_total is not None else "Hidden",
            "Target total": str(item.target_total) if st.session_state.privacy_reveal and item.target_total is not None else "Hidden",
        })
    st.dataframe(pd.DataFrame(aggregate_rows), hide_index=True, width="stretch")


def render_export_page(
    report: ComparisonReport | None,
    source_bytes: bytes | None,
    target_bytes: bytes | None,
    source_name: str,
    target_name: str,
) -> None:
    st.markdown("## Export evidence")
    if report is None or source_bytes is None or target_bytes is None:
        st.markdown('<div class="empty-state">Run a comparison before exporting the audit pack.</div>', unsafe_allow_html=True)
        return
    st.markdown("The default package contains the mapping, row references, reconciliation report, and a findings CSV. Raw values are redacted.")
    include_inputs = st.checkbox(
        "Include the source and target CSV files in the ZIP",
        value=st.session_state.include_inputs_in_export,
        key="include_inputs_in_export",
        help="Optional. This makes the package reproducible without separately retaining the extracts, but it includes every raw value in both files.",
    )
    if include_inputs:
        st.markdown('<div class="privacy-note">The ZIP will contain both full CSV extracts. Store it as sensitive business data and avoid committing it to GitHub.</div>', unsafe_allow_html=True)
    pack = make_audit_pack(
        report,
        st.session_state.mapping_payload,
        source_bytes,
        target_bytes,
        source_name,
        target_name,
        include_inputs,
    )
    st.download_button(
        "Download audit pack",
        data=pack,
        file_name="migration-workbench-audit-pack.zip",
        mime="application/zip",
        type="primary",
        icon=":material/download:",
        width="stretch",
    )
    st.caption("Session data is held in memory. Downloaded report bundles are created on request; the app writes no permanent report file.")


def main() -> None:
    initialize_state()
    st.markdown(CSS, unsafe_allow_html=True)
    source_bytes, target_bytes, source_name, target_name = active_files()

    if not st.session_state.demo_autorun_done and st.session_state.dataset_mode == "Bundled synthetic example":
        # The starter screen runs only the repository's synthetic fixtures and is useful on first launch.
        try:
            run_and_store(source_bytes, target_bytes, source_name, target_name, st.session_state.mapping_payload)
        except Exception as exc:  # the initial synthetic example should fail visibly, not blank the app
            st.session_state.comparison_error = f"The bundled example could not run: {exc}"
        st.session_state.demo_autorun_done = True

    report = st.session_state.comparison_report
    if st.session_state.dataset_mode == "Upload CSV pair" and (source_bytes is None or target_bytes is None):
        report = None
        st.session_state.comparison_report = None
    elif source_bytes is not None and target_bytes is not None:
        signature = comparison_signature(
            source_bytes,
            target_bytes,
            source_name,
            target_name,
            st.session_state.mapping_payload,
        )
        if report is not None and st.session_state.run_signature != signature:
            clear_comparison_state()
            report = None

    clicked = display_header(source_name, target_name, source_bytes, target_bytes)
    if clicked and source_bytes is not None and target_bytes is not None:
        with st.status("Comparing extracts…", expanded=False) as status:
            run_and_store(source_bytes, target_bytes, source_name, target_name, st.session_state.mapping_payload)
            if st.session_state.get("comparison_error"):
                status.update(label="Comparison needs attention", state="error")
            else:
                status.update(label="Comparison complete", state="complete")
        report = st.session_state.comparison_report
    error = st.session_state.get("comparison_error")
    if error:
        st.error(error)
    render_review_page(report, source_bytes, target_bytes, source_name, target_name)


if __name__ == "__main__":
    main()

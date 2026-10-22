"""Create and print assets in bulk from CSV or Excel files."""

import json
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from core.database import save_bulk_issuances
from core.printer_service import load_config, send_multiple_asset_labels
from core.qr_generator import build_qr_payload


REQUIRED_COLUMNS = ("asset_name", "asset_code")
OPTIONAL_COLUMNS = (
    "asset_id",
    "issue_date",
    "issuer_name",
    "issued_to",
    "department",
    "location",
    "status",
    "mac_address",
    "ip_address",
    "hardware_id",
    "hostname",
    "model",
    "serial_number",
    "os",
    "manufacturer",
)
COLUMN_ALIASES = {
    "emp_id": "asset_id",
    "emp_name": "issued_to",
    "issued_by": "issuer_name",
    "model": "asset_name",
    "serial_number": "asset_code",
}


def _clean_cell(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _format_issue_date(value, fallback):
    value = _clean_cell(value)
    if not value:
        return fallback.isoformat()
    try:
        return pd.to_datetime(value, errors="raise").date().isoformat()
    except (TypeError, ValueError):
        raise ValueError(f"Invalid issue date: {value}")


def _read_asset_file(uploaded):
    if uploaded.name.lower().endswith(".csv"):
        frame = pd.read_csv(uploaded, dtype=str, keep_default_na=False)
    else:
        frame = pd.read_excel(uploaded, dtype=str, keep_default_na=False)
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    for old_name, new_name in COLUMN_ALIASES.items():
        if new_name not in frame.columns and old_name in frame.columns:
            frame[new_name] = frame[old_name]
    return frame


def render():
    st.header("Bulk Asset Issue")
    st.caption(
        "Upload a CSV or Excel file with manually entered asset details. "
        "System details are optional; nothing is auto-detected."
    )
    cfg = load_config()

    with st.expander("Download sample template"):
        sample = pd.DataFrame(
            [
                {
                    "asset_id": "AST001",
                    "asset_name": "Laptop",
                    "asset_code": "LAP001",
                    "issue_date": "2026-10-20",
                    "issuer_name": "Rahul Sharma",
                    "issued_to": "Manish Tiwari",
                    "department": "IT",
                    "location": "Head Office",
                    "status": "Issued",
                    "mac_address": "",
                    "ip_address": "",
                    "hardware_id": "",
                }
            ]
        )
        st.download_button(
            "Download CSV Template",
            sample.to_csv(index=False).encode("utf-8"),
            "asset_bulk_template.csv",
            "text/csv",
        )

    uploaded = st.file_uploader("Upload CSV / Excel", type=["csv", "xlsx"])
    if uploaded is None:
        return

    try:
        frame = _read_asset_file(uploaded)
    except (OSError, UnicodeError, ValueError, ImportError) as error:
        st.error(f"Could not read the uploaded file: {error}")
        return

    if frame.empty:
        st.warning("The uploaded file has no asset rows.")
        return

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        st.error(
            "Missing required columns: "
            + ", ".join(missing)
            + ". Download the sample template to see the expected format."
        )
        return

    for column in OPTIONAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""

    frame = frame.loc[:, list(REQUIRED_COLUMNS) + list(OPTIONAL_COLUMNS)]
    invalid_rows = [
        str(index + 2)
        for index, row in frame.iterrows()
        if not _clean_cell(row["asset_name"]) or not _clean_cell(row["asset_code"])
    ]
    if invalid_rows:
        st.error(
            "Asset Name and Asset Code are required. Check spreadsheet rows: "
            + ", ".join(invalid_rows)
        )
        return

    st.success(f"Loaded {len(frame)} assets")
    st.dataframe(frame, use_container_width=True)
    default_date = st.date_input("Default issue date", value=date.today())
    default_issuer = st.text_input(
        "Default issuer name (used if blank in a row)",
        value=cfg.get("default_issuer", "IT Admin"),
    )
    if not st.button(
        "Generate QR and Print All",
        type="primary",
        use_container_width=True,
    ):
        return

    try:
        for value in frame["issue_date"]:
            _format_issue_date(value, default_date)
    except ValueError as error:
        st.error(str(error))
        return

    jobs = []
    records = []
    progress = st.progress(0, text="Preparing asset labels...")
    for index, row in frame.iterrows():
        data = {column: _clean_cell(row[column]) for column in OPTIONAL_COLUMNS}
        data["asset_name"] = _clean_cell(row["asset_name"])
        data["asset_code"] = _clean_cell(row["asset_code"])
        data["issue_date"] = _format_issue_date(row["issue_date"], default_date)
        data["issuer_name"] = data["issuer_name"] or default_issuer.strip()
        data["status"] = data["status"] or "Issued"
        payload = build_qr_payload(data)
        qr_string = json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False
        )
        data["qr_payload"] = qr_string
        records.append(data)
        jobs.append(
            {
                "qr_payload": qr_string,
                "emp_name": data["asset_name"],
                "emp_id": data["asset_id"] or data["asset_code"],
            }
        )
        progress.progress(
            (index + 1) / len(frame),
            text=f"Prepared {index + 1}/{len(frame)}",
        )

    with st.spinner("Printing asset labels..."):
        summary = send_multiple_asset_labels(jobs)
    try:
        save_bulk_issuances(records)
    except (sqlite3.Error, OSError, TypeError, ValueError) as error:
        st.error(
            f"Print finished ({summary['success']} succeeded, {summary['failed']} "
            f"failed), but the database could not save the uploaded assets: {error}"
        )
        return

    st.success(
        f"Done. Total: {summary['total']} | "
        f"Printed: {summary['success']} | Failed: {summary['failed']} | "
        f"Saved: {len(records)}"
    )
    if summary["errors"]:
        with st.expander("View print errors"):
            for error in summary["errors"]:
                st.error(error)

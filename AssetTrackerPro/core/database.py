"""SQLite persistence for asset issuance records."""

import os
import sqlite3
from datetime import datetime

from core.qr_generator import build_qr_payload


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "assets.db")

OPTIONAL_DB_FIELDS = (
    "department",
    "location",
    "ip_address",
    "hardware_id",
)


def get_connection():
    """Return a SQLite connection and create the data directory if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the asset table and migrate existing laptop-issuance databases."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS issuances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_name TEXT NOT NULL DEFAULT '',
                emp_id TEXT NOT NULL DEFAULT '',
                issued_by TEXT,
                issue_date TEXT,
                hostname TEXT,
                model TEXT,
                serial_number TEXT,
                mac_address TEXT,
                os TEXT,
                manufacturer TEXT,
                qr_payload TEXT,
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                asset_id TEXT,
                asset_name TEXT,
                asset_code TEXT,
                issuer_name TEXT,
                issued_to TEXT,
                department TEXT,
                location TEXT,
                asset_status TEXT,
                ip_address TEXT,
                hardware_id TEXT
            )
            """
        )
        existing_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(issuances)")
        }
        new_columns = {
            "asset_id": "TEXT",
            "asset_name": "TEXT",
            "asset_code": "TEXT",
            "issuer_name": "TEXT",
            "issued_to": "TEXT",
            "department": "TEXT",
            "location": "TEXT",
            "asset_status": "TEXT",
            "ip_address": "TEXT",
            "hardware_id": "TEXT",
        }
        for column, column_type in new_columns.items():
            if column not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE issuances ADD COLUMN {column} {column_type}"
                )

        cursor.execute(
            """
            UPDATE issuances
            SET asset_id = COALESCE(NULLIF(asset_id, ''), emp_id, ''),
                asset_name = COALESCE(NULLIF(asset_name, ''), model, ''),
                asset_code = COALESCE(NULLIF(asset_code, ''), serial_number, ''),
                issuer_name = COALESCE(NULLIF(issuer_name, ''), issued_by, ''),
                issued_to = COALESCE(NULLIF(issued_to, ''), emp_name, ''),
                asset_status = COALESCE(NULLIF(asset_status, ''), 'Issued')
            WHERE asset_id IS NULL OR asset_name IS NULL OR asset_code IS NULL
               OR issuer_name IS NULL OR issued_to IS NULL OR asset_status IS NULL
               OR asset_id = '' OR asset_name = '' OR asset_code = ''
               OR issuer_name = '' OR issued_to = '' OR asset_status = ''
            """
        )
        connection.commit()
    finally:
        connection.close()


def normalize_asset_data(data):
    """Return canonical QR fields from new data or a legacy database row."""
    return build_qr_payload(dict(data))


def _legacy_fields(data):
    asset = normalize_asset_data(data)
    return {
        **asset,
        "emp_name": asset["issued_to"] or asset["asset_name"],
        "emp_id": asset["asset_id"] or asset["asset_code"],
        "issued_by": asset["issuer_name"],
        "hostname": str(data.get("hostname", "") or "").strip(),
        "model": str(data.get("model", "") or asset["asset_name"]).strip(),
        "serial_number": str(
            data.get("serial_number", "") or asset["asset_code"]
        ).strip(),
        "mac_address": asset.get("mac_address", ""),
        "os": asset.get("os", ""),
        "manufacturer": asset.get("manufacturer", ""),
        "ip_address": asset.get("ip_address", ""),
        "hardware_id": asset.get("hardware_id", ""),
    }


def _insert_record(cursor, data, qr_payload, now):
    asset = _legacy_fields(data)
    cursor.execute(
        """
        INSERT INTO issuances (
            emp_name, emp_id, issued_by, issue_date, hostname, model,
            serial_number, mac_address, os, manufacturer, qr_payload, status,
            created_at, updated_at, asset_id, asset_name, asset_code,
            issuer_name, issued_to, department, location, asset_status,
            ip_address, hardware_id
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?
        )
        """,
        (
            asset["emp_name"],
            asset["emp_id"],
            asset["issued_by"],
            asset["issue_date"],
            asset["hostname"],
            asset["model"],
            asset["serial_number"],
            asset["mac_address"],
            asset["os"],
            asset["manufacturer"],
            qr_payload,
            now,
            now,
            asset["asset_id"],
            asset["asset_name"],
            asset["asset_code"],
            asset["issuer_name"],
            asset["issued_to"],
            asset["department"],
            asset["location"],
            asset["status"],
            asset["ip_address"],
            asset["hardware_id"],
        ),
    )


def save_issuance(data, qr_payload=""):
    """Save one asset and preserve the legacy columns during migration."""
    init_db()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not qr_payload:
            import json

            qr_payload = json.dumps(
                normalize_asset_data(data), separators=(",", ":"), ensure_ascii=False
            )
        _insert_record(cursor, data, qr_payload, now)
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def save_bulk_issuances(records):
    """Save multiple asset records in one transaction."""
    init_db()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import json

        for record in records:
            qr_payload = record.get("qr_payload", "")
            if not qr_payload:
                qr_payload = json.dumps(
                    normalize_asset_data(record),
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            _insert_record(cursor, record, qr_payload, now)
        connection.commit()
        return len(records)
    finally:
        connection.close()


def get_all_issuances(status="ACTIVE"):
    """Fetch issuance records, newest first."""
    init_db()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        if status:
            cursor.execute(
                "SELECT * FROM issuances WHERE status = ? ORDER BY id DESC",
                (status,),
            )
        else:
            cursor.execute("SELECT * FROM issuances ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def search_issuances(query="", status="ACTIVE"):
    """Search active assets across identifiers, people, and optional device data."""
    if not query or not str(query).strip():
        return get_all_issuances(status)

    init_db()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        search_value = f"%{str(query).strip()}%"
        cursor.execute(
            """
            SELECT * FROM issuances
            WHERE (status = ? OR ? = '')
              AND (
                asset_id LIKE ? OR asset_name LIKE ? OR asset_code LIKE ?
                OR issuer_name LIKE ? OR issued_to LIKE ? OR department LIKE ?
                OR location LIKE ? OR ip_address LIKE ? OR hardware_id LIKE ?
                OR emp_name LIKE ? OR emp_id LIKE ? OR hostname LIKE ?
                OR model LIKE ? OR serial_number LIKE ? OR mac_address LIKE ?
                OR issued_by LIKE ?
              )
            ORDER BY id DESC
            """,
            (status, status, *([search_value] * 16)),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def get_issuance_by_id(record_id):
    """Fetch one record by database id."""
    init_db()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM issuances WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def update_issuance(record_id, data, qr_payload=""):
    """Update canonical asset fields and their legacy equivalents."""
    init_db()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import json

        asset = _legacy_fields(data)
        if not qr_payload:
            qr_payload = json.dumps(
                normalize_asset_data(data), separators=(",", ":"), ensure_ascii=False
            )
        cursor.execute(
            """
            UPDATE issuances SET
                emp_name = ?, emp_id = ?, issued_by = ?, issue_date = ?,
                hostname = ?, model = ?, serial_number = ?, mac_address = ?,
                os = ?, manufacturer = ?, qr_payload = ?, updated_at = ?,
                asset_id = ?, asset_name = ?, asset_code = ?, issuer_name = ?,
                issued_to = ?, department = ?, location = ?, asset_status = ?,
                ip_address = ?, hardware_id = ?
            WHERE id = ?
            """,
            (
                asset["emp_name"],
                asset["emp_id"],
                asset["issued_by"],
                asset["issue_date"],
                asset["hostname"],
                asset["model"],
                asset["serial_number"],
                asset["mac_address"],
                asset["os"],
                asset["manufacturer"],
                qr_payload,
                now,
                asset["asset_id"],
                asset["asset_name"],
                asset["asset_code"],
                asset["issuer_name"],
                asset["issued_to"],
                asset["department"],
                asset["location"],
                asset["status"],
                asset["ip_address"],
                asset["hardware_id"],
                record_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def delete_issuance(record_id):
    """Soft-delete a record without changing its issue status."""
    init_db()
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE issuances SET status = 'INACTIVE' WHERE id = ?", (record_id,)
        )
        connection.commit()
    finally:
        connection.close()


insert_issuance = save_issuance
insert_bulk_issuances = save_bulk_issuances
fetch_all_issuances = get_all_issuances
get_history = get_all_issuances

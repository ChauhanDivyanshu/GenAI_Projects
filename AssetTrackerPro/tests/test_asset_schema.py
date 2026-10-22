import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core import database, printer_service
from core.qr_generator import build_qr_payload


class AssetQrPayloadTests(unittest.TestCase):
    def test_builds_full_name_schema_and_omits_blank_optional_fields(self):
        payload = build_qr_payload(
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
                "ip_address": "192.0.2.10",
            }
        )

        self.assertEqual(
            {key: payload[key] for key in (
                "asset_id",
                "asset_name",
                "asset_code",
                "issue_date",
                "issuer_name",
                "issued_to",
                "department",
                "location",
                "status",
            )},
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
            },
        )
        self.assertNotIn("mac_address", payload)
        self.assertEqual(payload["ip_address"], "192.0.2.10")

    def test_old_square_default_config_is_migrated_to_measured_roll(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = os.path.join(directory, "config.json")
            with open(config_path, "w", encoding="utf-8") as config_file:
                json.dump(
                    {
                        "label_width_mm": 101.6,
                        "label_height_mm": 101.6,
                        "qr_module_size": 4,
                    },
                    config_file,
                )

            with patch.object(
                printer_service, "_config_path", return_value=config_path
            ):
                config = printer_service.load_config()

        self.assertEqual(config["label_width_mm"], 44)
        self.assertEqual(config["label_height_mm"], 45)
        self.assertEqual(config["qr_module_size"], 3)

    def test_database_soft_delete_status_does_not_replace_asset_status(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = os.path.join(directory, "assets.db")
            with patch.object(database, "DB_PATH", db_path):
                record_id = database.save_issuance(
                    {
                        "asset_id": "AST001",
                        "asset_name": "Laptop",
                        "asset_code": "LAP001",
                        "status": "Available",
                    }
                )
                record = database.get_issuance_by_id(record_id)
                payload = json.loads(record["qr_payload"])

                self.assertEqual(record["status"], "ACTIVE")
                self.assertEqual(record["asset_status"], "Available")
                self.assertEqual(payload["status"], "Available")

                database.delete_issuance(record_id)
                deleted = database.get_issuance_by_id(record_id)
                self.assertEqual(deleted["status"], "INACTIVE")
                self.assertEqual(
                    build_qr_payload(deleted)["status"], "Available"
                )

    def test_migrates_legacy_columns_without_losing_active_status(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = os.path.join(directory, "legacy.db")
            connection = sqlite3.connect(db_path)
            connection.execute(
                """
                CREATE TABLE issuances (
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO issuances (
                    emp_name, emp_id, issued_by, issue_date, model, serial_number
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Manish Tiwari", "AST001", "Rahul Sharma", "2026-10-20", "Laptop", "LAP001"),
            )
            connection.commit()
            connection.close()

            with patch.object(database, "DB_PATH", db_path):
                database.init_db()
                migrated = database.get_issuance_by_id(1)
                payload = build_qr_payload(migrated)

                self.assertEqual(migrated["status"], "ACTIVE")
                self.assertEqual(migrated["asset_status"], "Issued")
                self.assertEqual(payload["asset_id"], "AST001")
                self.assertEqual(payload["asset_name"], "Laptop")
                self.assertEqual(payload["asset_code"], "LAP001")
                self.assertEqual(payload["issuer_name"], "Rahul Sharma")
                self.assertEqual(payload["issued_to"], "Manish Tiwari")


if __name__ == "__main__":
    unittest.main()

import base64
import hashlib
import socket
import threading
import unittest
from unittest.mock import patch

import qrcode

from core import printer_service


class _WebSocketTestReader:
    def __init__(self, sock, pending=b""):
        self.sock = sock
        self.pending = bytearray(pending)

    def _read_exact(self, count):
        while len(self.pending) < count:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("client disconnected")
            self.pending.extend(chunk)
        result = bytes(self.pending[:count])
        del self.pending[:count]
        return result

    def read_text(self):
        first, second = self._read_exact(2)
        length = second & 0x7F
        if length == 126:
            length = int.from_bytes(self._read_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(self._read_exact(8), "big")
        mask = self._read_exact(4) if second & 0x80 else b""
        payload = self._read_exact(length) if length else b""
        if mask:
            payload = bytes(
                byte ^ mask[index % 4] for index, byte in enumerate(payload)
            )
        if first & 0x0F == 0x8:
            return ""
        return payload.decode("utf-8")


def _send_server_text(sock, text):
    payload = text.encode("utf-8")
    frame = bytearray([0x81])
    if len(payload) <= 125:
        frame.append(len(payload))
    elif len(payload) <= 65535:
        frame.append(126)
        frame.extend(len(payload).to_bytes(2, "big"))
    else:
        frame.append(127)
        frame.extend(len(payload).to_bytes(8, "big"))
    frame.extend(payload)
    sock.sendall(frame)


class PrinterCommandTests(unittest.TestCase):
    def setUp(self):
        self.config = printer_service.DEFAULT_CONFIG.copy()
        self.payload = {
            "en": "A Person",
            "ei": "EMP001",
            "sn": "SERIAL001",
            "md": "Laptop Model",
            "mc": "00-11-22-33-44-55",
        }

    def test_builds_qr_and_text_commands_in_zm_format(self):
        commands = printer_service._build_print_commands(
            self.payload, "A Person", "EMP001", self.config
        )

        qr_command = next(
            command for command in commands if command.startswith("ZM_DrawBar2D_QR|")
        )
        self.assertEqual(
            qr_command.split("|")[-1],
            '{"en":"A Person","ei":"EMP001","sn":"SERIAL001",'
            '"md":"Laptop Model","mc":"00-11-22-33-44-55"}',
        )
        self.assertIn("ZM_SetLabelWidth|352", commands)
        self.assertIn("ZM_SetLabelHeight|360|16", commands)
        qr_parts = next(
            command.split("|")
            for command in commands
            if command.startswith("ZM_DrawBar2D_QR|")
        )
        qr_matrix = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=0,
        )
        qr_matrix.add_data(qr_parts[-1])
        qr_matrix.make(fit=True)
        qr_side = (qr_matrix.modules_count + 8) * self.config["qr_module_size"]
        qr_x, qr_y = int(qr_parts[1]), int(qr_parts[2])
        self.assertGreaterEqual(qr_x, printer_service._dots(2, self.config["dpi"]))
        self.assertLessEqual(qr_x + qr_side, 352 - printer_service._dots(2, self.config["dpi"]))
        self.assertGreaterEqual(qr_y, printer_service._dots(2, self.config["dpi"]))
        self.assertLessEqual(qr_y + qr_side, 359 - printer_service._dots(2, self.config["dpi"]))
        self.assertTrue(
            any("|A1|Infosware IT Assets" in command for command in commands)
        )
        self.assertTrue(
            any("Laptop Model - SERIAL001" in command for command in commands)
        )
        self.assertTrue(all("RFID" not in command for command in commands))

    def test_rejects_pipe_in_qr_payload(self):
        with self.assertRaisesRegex(ValueError, "reserved by ZMPrintService"):
            printer_service._build_print_commands(
                {"en": "A|Person"}, "A Person", "EMP001", self.config
            )

    def test_prints_canonical_asset_and_recipient_details(self):
        payload = {
            "asset_id": "AST001",
            "asset_name": "Laptop",
            "asset_code": "LAP001",
            "issue_date": "2026-10-20",
            "issuer_name": "Rahul Sharma",
            "issued_to": "Manish Tiwari",
            "department": "IT",
            "location": "Head Office",
            "status": "Issued",
            "mac_address": "00-11-22-33-44-55",
            "ip_address": "192.0.2.10",
            "hardware_id": "HW-001",
        }

        commands = printer_service._build_print_commands(
            payload, "Laptop", "AST001", self.config
        )
        text_commands = [
            command
            for command in commands
            if command.startswith("ZM_DrawTextTrueTypeW|")
        ]
        rendered_text = "\n".join(command.rsplit("|", 1)[-1] for command in text_commands)

        self.assertIn("Laptop - LAP001", rendered_text)
        self.assertNotIn("Issued To:", rendered_text)
        qr_command = next(
            command
            for command in commands
            if command.startswith("ZM_DrawBar2D_QR|")
        )
        self.assertIn('"issued_to":"Manish Tiwari"', qr_command)
        self.assertIn('"ip_address":"192.0.2.10"', qr_command)
        self.assertIn('"hardware_id":"HW-001"', qr_command)
        self.assertTrue(all("RFID" not in command for command in commands))

    def test_rejects_offsets_that_move_qr_outside_label(self):
        config = self.config.copy()
        config["alignment_x_mm"] = 40
        with self.assertRaisesRegex(ValueError, "outside the printable label"):
            printer_service._build_print_commands(
                self.payload, "A Person", "EMP001", config
            )

    def test_qr_is_centered_horizontally_on_label(self):
        commands = printer_service._build_print_commands(
            self.payload, "A Person", "EMP001", self.config
        )
        qr_command = next(
            command for command in commands if command.startswith("ZM_DrawBar2D_QR|")
        )
        qr_parts = qr_command.split("|")
        qr_matrix = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=0,
        )
        qr_matrix.add_data(qr_parts[-1])
        qr_matrix.make(fit=True)
        qr_side = (qr_matrix.modules_count + 8) * self.config["qr_module_size"]
        qr_x = int(qr_parts[1])
        label_width = printer_service._dots(44, self.config["dpi"])

        self.assertLessEqual(abs((qr_x + qr_side / 2) - label_width / 2), 1)

    def test_small_roll_defaults_fit_qr_with_top_header(self):
        commands = printer_service._build_print_commands(
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
            "Laptop",
            "AST001",
            printer_service.DEFAULT_CONFIG,
        )
        qr_command = next(
            command for command in commands if command.startswith("ZM_DrawBar2D_QR|")
        )
        _, x, y, *_ = qr_command.split("|")
        self.assertGreaterEqual(int(y), printer_service._dots(9, 203))
        self.assertTrue(any("LAP001" in command for command in commands))

    def test_company_and_asset_text_use_separate_zones_around_qr(self):
        commands = printer_service._build_print_commands(
            {
                "asset_id": "AST001",
                "asset_name": "Laptop",
                "asset_code": "LAP001",
                "status": "Issued",
            },
            "Laptop",
            "AST001",
            self.config,
        )
        qr = next(
            command.split("|")
            for command in commands
            if command.startswith("ZM_DrawBar2D_QR|")
        )
        texts = [
            command.split("|")
            for command in commands
            if command.startswith("ZM_DrawTextTrueTypeW|")
        ]
        self.assertEqual(len(texts), 2)
        qr_matrix = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=0,
        )
        qr_matrix.add_data(qr[-1])
        qr_matrix.make(fit=True)
        qr_top = int(qr[2])
        qr_bottom = qr_top + (qr_matrix.modules_count + 8) * self.config["qr_module_size"]
        company_top, company_size = int(texts[0][2]), int(texts[0][3])
        title_top, title_size = int(texts[1][2]), int(texts[1][3])

        self.assertEqual(company_top, printer_service._dots(2.5, self.config["dpi"]))
        self.assertLess(company_top + company_size, qr_top)
        self.assertLess(qr_bottom, title_top)
        self.assertGreaterEqual(qr_top - (company_top + company_size), printer_service._dots(2, self.config["dpi"]))
        self.assertGreaterEqual(title_top - qr_bottom, printer_service._dots(2, self.config["dpi"]))

    def test_header_and_asset_title_are_larger_and_centered(self):
        commands = printer_service._build_print_commands(
            {
                "asset_id": "AST001",
                "asset_name": "Laptop",
                "asset_code": "LAP001",
                "status": "Issued",
            },
            "Laptop",
            "AST001",
            self.config,
        )
        text_commands = [
            command.split("|")
            for command in commands
            if command.startswith("ZM_DrawTextTrueTypeW|")
        ]
        self.assertEqual(len(text_commands), 2)

        width_dots = printer_service._dots(44, self.config["dpi"])
        margin = printer_service._dots(2, self.config["dpi"])
        for text_command, minimum_size in zip(text_commands, (26, 22)):
            x = int(text_command[1])
            font_size = int(text_command[3])
            text = text_command[-1]
            estimated_width = int(len(text) * font_size * 0.64 + 0.5)
            expected_x = printer_service._centered_text_x(
                text, font_size, width_dots, margin
            )
            self.assertGreaterEqual(font_size, minimum_size)
            self.assertEqual(x, expected_x)
            self.assertLessEqual(abs((x + estimated_width / 2) - width_dots / 2), 1)


class BulkPrintTests(unittest.TestCase):
    @patch("core.printer_service.time.sleep")
    @patch("core.printer_service.print_asset_label")
    def test_returns_total_and_per_job_errors(self, print_asset_label, _sleep):
        print_asset_label.side_effect = [
            (True, "printed"),
            (False, "printer offline"),
        ]
        jobs = [
            {"qr_payload": "{}", "emp_name": "One", "emp_id": "EMP001"},
            {"qr_payload": "{}", "emp_name": "Two", "emp_id": "EMP002"},
        ]

        result = printer_service.send_multiple_asset_labels(jobs)

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["errors"], ["EMP002: printer offline"])


class PrinterSocketTests(unittest.TestCase):
    def test_zm_print_transaction_over_websocket(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        commands = []
        server_errors = []

        def serve():
            try:
                client, _ = server.accept()
                with client:
                    client.settimeout(3)
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        request.extend(client.recv(4096))
                    headers = bytes(request).split(b"\r\n\r\n", 1)[0]
                    key = next(
                        line.split(b":", 1)[1].strip()
                        for line in headers.split(b"\r\n")
                        if line.lower().startswith(b"sec-websocket-key:")
                    )
                    accept = base64.b64encode(
                        hashlib.sha1(
                            key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                        ).digest()
                    )
                    client.sendall(
                        b"HTTP/1.1 101 Switching Protocols\r\n"
                        b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                        b"Sec-WebSocket-Accept: "
                        + accept
                        + b"\r\n\r\n"
                    )
                    reader = _WebSocketTestReader(client)
                    while True:
                        command = reader.read_text()
                        if not command:
                            break
                        commands.append(command)
                        if command == "OpenPort|255":
                            _send_server_text(client, "OpenPort:0")
                        elif command == "ZM_GetPrinterStatus_USB|500":
                            _send_server_text(client, "PrinterStatus_USB:0")
                        elif command == "ZM_PrintLabel|1|1":
                            _send_server_text(client, "打印完成(Print finished).")
                        elif command == "ClosePort":
                            break
            except Exception as error:
                server_errors.append(error)
            finally:
                server.close()

        thread = threading.Thread(target=serve)
        thread.start()
        config = printer_service.DEFAULT_CONFIG.copy()
        config["ws_port"] = port

        try:
            ok, message = printer_service.print_via_zm_service(
                self._payload(), "Alignment Test", "TEST-0001", config
            )
        finally:
            thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(server_errors, [])
        self.assertTrue(ok, message)
        self.assertIn("ZM_GetPrinterStatus_USB|500", commands)
        self.assertIn("ZM_PrintLabel|1|1", commands)
        self.assertIn("ClosePort", commands)
        self.assertTrue(any(command.startswith("ZM_DrawBar2D_QR|") for command in commands))
        self.assertFalse(any("RFID" in command for command in commands))

    @staticmethod
    def _payload():
        return {
            "en": "Alignment Test",
            "ei": "TEST-0001",
            "sn": "SAMPLE-SERIAL",
            "md": "Sample Laptop",
            "mc": "00-11-22-33-44-55",
            "os": "Windows",
        }


if __name__ == "__main__":
    unittest.main()

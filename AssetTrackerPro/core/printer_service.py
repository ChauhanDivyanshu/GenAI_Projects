"""QR label printing through the bundled ZMPrintService WebSocket service."""

import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import time

import qrcode


DEFAULT_CONFIG = {
    "ws_host": "127.0.0.1",
    "ws_port": 1808,
    "dpi": 203,
    "label_width_mm": 44,
    "label_height_mm": 45,
    "label_gap_mm": 2,
    "print_speed": 2,
    "print_darkness": 14,
    "qr_module_size": 3,
    "alignment_x_mm": 0,
    "alignment_y_mm": 0,
    "company_name": "Infosware IT Assets",
    "default_issuer": "IT Admin",
    "print_timeout_ms": 18000,
    "zm_service_path": "",
}


def _app_directories():
    if getattr(sys, "frozen", False):
        candidates = [getattr(sys, "_MEIPASS", ""), os.path.dirname(sys.executable)]
    else:
        candidates = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    return list(dict.fromkeys(path for path in candidates if path))


def _config_path():
    return os.path.join(_app_directories()[0], "config.json")


def load_config():
    """Load app settings and apply defaults for settings added in newer versions."""
    config_path = _config_path()
    if not os.path.isfile(config_path):
        return DEFAULT_CONFIG.copy()

    with open(config_path, "r", encoding="utf-8-sig") as config_file:
        saved_config = json.load(config_file)
    if not isinstance(saved_config, dict):
        raise ValueError("config.json must contain a JSON object.")
    config = {**DEFAULT_CONFIG, **saved_config}
    if (
        float(config.get("label_width_mm", 0)) == 101.6
        and float(config.get("label_height_mm", 0)) == 101.6
    ):
        config["label_width_mm"] = DEFAULT_CONFIG["label_width_mm"]
        config["label_height_mm"] = DEFAULT_CONFIG["label_height_mm"]
        if int(config.get("qr_module_size", 0)) == 4:
            config["qr_module_size"] = DEFAULT_CONFIG["qr_module_size"]
    return config


def save_config(cfg):
    """Save settings as UTF-8 JSON."""
    config_path = _config_path()
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(cfg, config_file, indent=2, ensure_ascii=False)


def _is_process_running(process_name="ZMPrintService.exe"):
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and process_name.lower() in result.stdout.lower()


def is_zm_service_up(host="127.0.0.1", port=1808, timeout_ms=1000):
    try:
        with socket.create_connection(
            (host, int(port)), timeout=max(1, timeout_ms) / 1000.0
        ):
            return True
    except (OSError, TypeError, ValueError):
        return False


def _service_candidates(config):
    custom_path = str(config.get("zm_service_path", "")).strip()
    candidates = [custom_path] if custom_path else []
    for directory in _app_directories():
        candidates.extend(
            [
                os.path.join(directory, "ZMPrintService.exe"),
                os.path.join(directory, "tools", "ZMPrintService.exe"),
            ]
        )
    candidates.append(r"C:\Program Files\ZMPrintService\ZMPrintService.exe")
    return list(dict.fromkeys(path for path in candidates if path))


def launch_zm_service():
    """Start the bundled ZMPrintService and verify that its WebSocket port opens."""
    config = load_config()
    host = config["ws_host"]
    port = config["ws_port"]

    if is_zm_service_up(host, port):
        return True, "ZMPrintService is ready."
    if _is_process_running():
        return False, (
            "ZMPrintService.exe is running, but its WebSocket listener is not "
            f"available at {host}:{port}. Check the service port in its tray settings."
        )

    service_path = next(
        (path for path in _service_candidates(config) if os.path.isfile(path)), None
    )
    if service_path is None:
        return False, (
            "ZMPrintService.exe was not found. Keep it next to AssetTrackerPro or "
            "set its path in Settings."
        )

    try:
        subprocess.Popen(
            [service_path],
            cwd=os.path.dirname(service_path),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as error:
        return False, f"Could not start ZMPrintService: {error}"

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if is_zm_service_up(host, port, timeout_ms=500):
            return True, f"ZMPrintService started from {service_path}."
        time.sleep(0.25)

    return False, (
        f"ZMPrintService started, but {host}:{port} did not become available. "
        "Confirm the service port and printer connection."
    )


def check_printer_status():
    config = load_config()
    host = config["ws_host"]
    port = config["ws_port"]
    return {
        "protocol": "ZMPrintService USB / QR",
        "ws_online": is_zm_service_up(host, port, timeout_ms=1500),
        "process_active": _is_process_running(),
        "ws_url": f"ws://{host}:{port}",
    }


def _normalize_qr_payload(payload):
    if isinstance(payload, dict):
        payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    elif not isinstance(payload, str):
        raise TypeError("QR payload must be a string or a dictionary.")

    if not payload.strip():
        raise ValueError("QR payload cannot be empty.")
    if "|" in payload or "\r" in payload or "\n" in payload:
        raise ValueError(
            "QR payload contains a character reserved by ZMPrintService "
            "('|', CR, or LF). Remove it before printing."
        )
    return payload


def _safe_label_text(value):
    text = str(value or "")
    return " ".join(text.replace("|", "/").split())


def _dots(mm, dpi):
    return int(float(mm) * int(dpi) / 25.4 + 0.5)


def _fit_label_text(value, preferred_size, max_width):
    text = _safe_label_text(value)
    if not text:
        return "", preferred_size

    font_size = min(preferred_size, int(max_width / (len(text) * 0.64)))
    if font_size < 12:
        max_chars = max(1, int(max_width / (12 * 0.64)))
        text = text[: max(1, max_chars - 3)] + "..."
        font_size = 12
    return text, font_size


def _centered_text_x(text, font_size, width_dots, margin):
    estimated_width = int(len(text) * font_size * 0.64 + 0.5)
    return max(margin, (width_dots - estimated_width) // 2)


def _build_print_commands(qr_payload, emp_name, emp_id, config):
    """Build QR and label text commands within the configured tag dimensions."""
    dpi = int(config["dpi"])
    label_width = float(config["label_width_mm"])
    label_height = float(config["label_height_mm"])
    gap = float(config.get("label_gap_mm", 0))
    qr_text = _normalize_qr_payload(qr_payload)
    module_size = int(config["qr_module_size"])
    speed = int(config["print_speed"])
    darkness = int(config["print_darkness"])
    if dpi <= 0 or label_width <= 0 or label_height <= 0 or gap < 0:
        raise ValueError("DPI and label dimensions must be positive; gap cannot be negative.")
    if not 2 <= speed <= 8 or not 0 <= darkness <= 20:
        raise ValueError("Print speed must be 2-8 and darkness must be 0-20.")
    if not 1 <= module_size <= 10:
        raise ValueError("QR module size must be between 1 and 10 dots.")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=0,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)
    qr_side_dots = (qr.modules_count + 8) * module_size

    width_dots = _dots(label_width, dpi)
    height_dots = _dots(label_height, dpi)
    gap_dots = _dots(gap, dpi)
    margin = _dots(2, dpi)
    offset_x = _dots(config.get("alignment_x_mm", 0), dpi)
    offset_y = _dots(config.get("alignment_y_mm", 0), dpi)
    qr_x = (width_dots - qr_side_dots) // 2 + offset_x
    header_height = _dots(9, dpi)
    available_qr_height = height_dots - margin - header_height
    qr_y = header_height + max(
        0, (available_qr_height - qr_side_dots) // 2
    ) + offset_y

    if qr_side_dots + margin * 2 > min(width_dots, height_dots):
        raise ValueError(
            "This QR payload and module size do not fit the configured label. "
            "Use a larger label, reduce QR module size, or shorten the asset details."
        )
    if (
        qr_x < margin
        or qr_x + qr_side_dots > width_dots - margin
        or qr_y < margin
        or qr_y + qr_side_dots > height_dots - margin
    ):
        raise ValueError(
            "QR alignment offsets place the QR outside the printable label. "
            "Reset the X/Y alignment offsets or use a larger label."
        )

    decoded = {}
    try:
        candidate = json.loads(qr_text)
        if isinstance(candidate, dict):
            decoded = candidate
    except json.JSONDecodeError:
        pass

    asset_name = decoded.get("asset_name", decoded.get("md", emp_name))
    asset_code = decoded.get("asset_code", decoded.get("sn", emp_id))
    title_text = f"{asset_name} - {asset_code}".strip(" -")

    max_text_width = width_dots - margin * 2
    text_rows = []
    company, company_size = _fit_label_text(
        config["company_name"], 26, max_text_width
    )
    company_y = 2.5
    text_rows.append((company_y, company_size, company))
    title, title_size = _fit_label_text(title_text, 22, max_text_width)
    title_y = (height_dots - margin - title_size) * 25.4 / dpi
    text_rows.append((title_y, title_size, title))

    commands = [
        "ZM_ClearBuffer",
        f"ZM_SetPrintSpeed|{speed}",
        f"ZM_SetDarkness|{darkness}",
        f"ZM_SetLabelWidth|{width_dots}",
        f"ZM_SetLabelHeight|{height_dots}|{gap_dots}",
        (
            f"ZM_DrawBar2D_QR|{qr_x}|{qr_y}"
            f"|0|0|0|{module_size}|4|0|8|{qr_text}"
        ),
    ]
    for index, (y_mm, font_size, text) in enumerate(text_rows):
        if text:
            y = _dots(y_mm, dpi) + offset_y
            text_x = _centered_text_x(text, font_size, width_dots, margin) + offset_x
            estimated_width = int(len(text) * font_size * 0.64 + 0.5)
            if (
                y < margin
                or y + font_size > height_dots - margin
                or text_x < margin
                or text_x + estimated_width > width_dots - margin
            ):
                raise ValueError(
                    "Text alignment offsets place label text outside the printable area."
                )
            commands.append(
                f"ZM_DrawTextTrueTypeW|{text_x}|{y}|{font_size}|0|Arial|1|600"
                f"|0|0|0|A{index + 1}|{text}"
            )
    return commands


class _WebSocketConnection:
    def __init__(self, sock, pending=b""):
        self.sock = sock
        self.pending = bytearray(pending)

    def _read_exact(self, count, deadline):
        while len(self.pending) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout("Timed out waiting for ZMPrintService.")
            self.sock.settimeout(remaining)
            chunk = self.sock.recv(max(4096, count - len(self.pending)))
            if not chunk:
                raise ConnectionError("ZMPrintService closed the connection.")
            self.pending.extend(chunk)
        result = bytes(self.pending[:count])
        del self.pending[:count]
        return result

    def send_frame(self, opcode, payload=b""):
        mask = os.urandom(4)
        length = len(payload)
        frame = bytearray([0x80 | opcode])
        if length <= 125:
            frame.append(0x80 | length)
        elif length <= 65535:
            frame.append(0x80 | 126)
            frame.extend(length.to_bytes(2, "big"))
        else:
            frame.append(0x80 | 127)
            frame.extend(length.to_bytes(8, "big"))
        frame.extend(mask)
        frame.extend(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(frame)

    def send_text(self, text):
        self.send_frame(0x1, text.encode("utf-8"))

    def receive_text(self, timeout):
        deadline = time.monotonic() + timeout
        fragments = bytearray()
        message_opcode = None
        while True:
            first, second = self._read_exact(2, deadline)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = int.from_bytes(self._read_exact(2, deadline), "big")
            elif length == 127:
                length = int.from_bytes(self._read_exact(8, deadline), "big")
            mask = self._read_exact(4, deadline) if masked else b""
            payload = self._read_exact(length, deadline) if length else b""
            if masked:
                payload = bytes(
                    byte ^ mask[index % 4] for index, byte in enumerate(payload)
                )

            if opcode == 0x8:
                raise ConnectionError("ZMPrintService closed the WebSocket.")
            if opcode == 0x9:
                self.send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2):
                message_opcode = opcode
            elif opcode != 0x0:
                continue
            fragments.extend(payload)
            if final:
                if message_opcode != 0x1:
                    continue
                return fragments.decode("utf-8", errors="replace")


def _connect_websocket(host, port, timeout):
    sock = socket.create_connection((host, int(port)), timeout=timeout)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(request.encode("ascii"))
    response = bytearray()
    while b"\r\n\r\n" not in response:
        sock.settimeout(timeout)
        chunk = sock.recv(4096)
        if not chunk:
            sock.close()
            raise ConnectionError("ZMPrintService ended the WebSocket handshake.")
        response.extend(chunk)
        if len(response) > 16384:
            sock.close()
            raise ConnectionError("ZMPrintService returned an oversized handshake.")

    header, pending = bytes(response).split(b"\r\n\r\n", 1)
    lines = header.decode("iso-8859-1").split("\r\n")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()

    expected_accept = base64.b64encode(
        hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
        ).digest()
    ).decode("ascii")
    if (
        not lines[0].startswith("HTTP/1.1 101")
        or headers.get("sec-websocket-accept") != expected_accept
    ):
        sock.close()
        raise ConnectionError("ZMPrintService rejected the WebSocket handshake.")
    return _WebSocketConnection(sock, pending)


def _wait_for_message(connection, timeout, prefix):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            message = connection.receive_text(max(0.01, deadline - time.monotonic()))
        except socket.timeout:
            return None
        if message.startswith("Error:"):
            raise RuntimeError(message)
        if message.startswith(prefix):
            return message
    return None


def print_via_zm_service(qr_payload, emp_name, emp_id, config):
    """Print one QR asset label using ZMPrintService's documented WebSocket API."""
    timeout = max(1, int(config["print_timeout_ms"])) / 1000.0
    host = config["ws_host"]
    port = int(config["ws_port"])
    try:
        commands = _build_print_commands(qr_payload, emp_name, emp_id, config)
        connection = _connect_websocket(host, port, timeout)
        try:
            connection.send_text("OpenPort|255")
            opened = _wait_for_message(connection, min(timeout, 5), "OpenPort:")
            if opened is None or not opened.endswith(":0"):
                return False, (
                    f"ZMPrintService could not open the USB printer "
                    f"({opened or 'no response'}). Check the printer connection."
                )

            connection.send_text("ZM_GetPrinterStatus_USB|500")
            status = _wait_for_message(connection, min(timeout, 5), "PrinterStatus_USB:")
            if status is None:
                return False, "ZMPrintService did not return the USB printer status."
            status_code = status.partition(":")[2].strip()
            if status_code != "0":
                messages = {
                    "82": "Printer ribbon/carbon belt error.",
                    "83": "Printer label/paper error.",
                    "88": "Printer is paused.",
                    "-1007": "Printer USB port is unavailable.",
                }
                return False, messages.get(
                    status_code, f"Printer status is abnormal (code {status_code})."
                )

            for command in commands:
                connection.send_text(command)
            connection.send_text("ZM_PrintLabel|1|1")

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    message = connection.receive_text(
                        max(0.01, deadline - time.monotonic())
                    )
                except socket.timeout:
                    break
                if message.startswith("Error:"):
                    return False, f"ZMPrintService rejected a print command: {message}"
                lowered = message.lower()
                if (
                    "zm_printlabel_complete:" in lowered
                    or "print finished" in lowered
                    or "print complete" in lowered
                    or "打印完成" in message
                ):
                    return True, "QR label printed successfully via ZMPrintService."
            return False, "ZMPrintService did not confirm that the QR label printed."
        finally:
            try:
                connection.send_text("ClosePort")
            except OSError:
                pass
            connection.sock.close()
    except (OSError, RuntimeError, TypeError, ValueError, ConnectionError) as error:
        return False, f"ZMPrintService error: {error}"


def print_asset_label(qr_payload, emp_name, emp_id):
    config = load_config()
    host = config["ws_host"]
    port = int(config["ws_port"])
    if not is_zm_service_up(host, port):
        started, message = launch_zm_service()
        if not started:
            return False, message
    return print_via_zm_service(qr_payload, emp_name, emp_id, config)


def send_multiple_asset_labels(jobs):
    results = {"total": len(jobs), "success": 0, "failed": 0, "errors": []}
    for index, job in enumerate(jobs):
        try:
            ok, message = print_asset_label(
                job["qr_payload"], job["emp_name"], job["emp_id"]
            )
        except (KeyError, TypeError, ValueError) as error:
            ok, message = False, f"Invalid print job: {error}"
        if ok:
            results["success"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(f"{job.get('emp_id', 'Unknown ID')}: {message}")
        if index < len(jobs) - 1:
            time.sleep(0.5)
    return results

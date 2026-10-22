"""Build and render self-contained asset QR payloads."""

import json

import qrcode


ASSET_FIELDS = (
    "asset_id",
    "asset_name",
    "asset_code",
    "issue_date",
    "issuer_name",
    "issued_to",
    "department",
    "location",
    "status",
)
OPTIONAL_FIELDS = (
    "mac_address",
    "ip_address",
    "hardware_id",
    "hostname",
    "model",
    "serial_number",
    "os",
    "manufacturer",
)


def _value(data, *keys):
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_qr_payload(data, *args, **kwargs):
    """Return the requested full-name JSON schema, omitting blank optional fields.

    The legacy field aliases let records already stored in the app continue to
    produce valid QR codes after the asset-management schema update.
    """
    if not isinstance(data, dict):
        raise TypeError("Asset QR data must be provided as a dictionary.")

    asset = {
        "asset_id": _value(data, "asset_id", "assetId", "emp_id", "ei"),
        "asset_name": _value(data, "asset_name", "assetName", "model", "md"),
        "asset_code": _value(
            data, "asset_code", "assetCode", "serial_number", "sn"
        ),
        "issue_date": _value(data, "issue_date", "issueDate", "dt"),
        "issuer_name": _value(data, "issuer_name", "issuerName", "issued_by", "ib"),
        "issued_to": _value(data, "issued_to", "issuedTo", "emp_name", "en"),
        "department": _value(data, "department"),
        "location": _value(data, "location"),
        "status": _value(data, "asset_status", "status") or "Issued",
    }

    for field in OPTIONAL_FIELDS:
        value = _value(data, field)
        if field == "mac_address" and not value:
            value = _value(data, "mac", "mc")
        elif field == "ip_address" and not value:
            value = _value(data, "ip", "ipAddress")
        elif field == "hardware_id" and not value:
            value = _value(data, "hardwareId", "hardware_identifier")
        if value:
            asset[field] = value
    return asset


generate_qr_payload = build_qr_payload


def generate_qr_image(payload, box_size=10, border=4):
    """Generate a PIL image for displaying the QR payload in Streamlit."""
    if isinstance(payload, dict):
        payload_string = json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False
        )
    else:
        payload_string = str(payload)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload_string)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    if hasattr(image, "get_image"):
        return image.get_image()
    return image.convert("RGB")

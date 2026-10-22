"""Create, preview, save, and print a single asset record."""

import datetime
import json

import streamlit as st

from core.database import save_issuance
from core.printer_service import load_config, print_asset_label
from core.qr_generator import build_qr_payload, generate_qr_image


ASSET_STATUSES = ("Issued", "Available", "In Repair", "Retired", "Lost")


def render():
    st.title("Single Asset")
    st.caption(
        "Enter asset details manually. MAC address, IP address, and hardware ID "
        "are optional."
    )
    cfg = load_config()

    with st.form("single_issue_form"):
        st.subheader("Asset details")
        col1, col2 = st.columns(2)
        with col1:
            asset_id = st.text_input("Asset ID")
            asset_name = st.text_input("Asset Name *", placeholder="Laptop")
            asset_code = st.text_input(
                "Asset Code / Laptop Code *", placeholder="LAP001"
            )
            issue_date = st.date_input(
                "Issue Date", value=datetime.date.today()
            )
        with col2:
            issuer_name = st.text_input(
                "Issuer Name", value=cfg.get("default_issuer", "IT Admin")
            )
            issued_to = st.text_input("Issued To", placeholder="Full name")
            department = st.text_input("Department")
            location = st.text_input("Location")
        status = st.selectbox("Status", ASSET_STATUSES, index=0)

        with st.expander("Optional laptop / system details"):
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                mac_address = st.text_input("MAC Address")
                ip_address = st.text_input("IP Address")
                hardware_id = st.text_input("Hardware ID")
                hostname = st.text_input("Hostname")
            with detail_col2:
                model = st.text_input("Model")
                serial_number = st.text_input("Serial Number")
                os_name = st.text_input("Operating System")
                manufacturer = st.text_input("Manufacturer")

        submitted = st.form_submit_button(
            "Generate QR & Preview", type="primary"
        )

    if submitted:
        if not asset_name.strip() or not asset_code.strip():
            st.error("Asset Name and Asset Code are required.")
            return

        data = {
            "asset_id": asset_id.strip(),
            "asset_name": asset_name.strip(),
            "asset_code": asset_code.strip(),
            "issue_date": issue_date.isoformat(),
            "issuer_name": issuer_name.strip(),
            "issued_to": issued_to.strip(),
            "department": department.strip(),
            "location": location.strip(),
            "status": status,
            "mac_address": mac_address.strip(),
            "ip_address": ip_address.strip(),
            "hardware_id": hardware_id.strip(),
            "hostname": hostname.strip(),
            "model": model.strip(),
            "serial_number": serial_number.strip(),
            "os": os_name.strip(),
            "manufacturer": manufacturer.strip(),
        }
        payload = build_qr_payload(data)
        st.session_state.current_payload = payload
        st.session_state.current_qr_img = generate_qr_image(payload)
        st.session_state.current_data = data

    if st.session_state.get("current_qr_img") is None:
        return

    st.divider()
    st.subheader("QR Preview & Action")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(
            st.session_state.current_qr_img,
            width=250,
            caption="Asset details in QR",
        )
    with col2:
        st.json(st.session_state.current_payload)
        print_col, save_col = st.columns(2)
        data = st.session_state.current_data
        qr_string = json.dumps(
            st.session_state.current_payload,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with print_col:
            if st.button("Print & Save Asset Tag", type="primary"):
                with st.spinner("Printing asset tag..."):
                    printed, message = print_asset_label(
                        qr_string,
                        data["asset_name"],
                        data["asset_id"] or data["asset_code"],
                    )
                try:
                    save_issuance(data, qr_string)
                except Exception as error:
                    st.error(
                        f"Print result: {message}. Could not save asset record: {error}"
                    )
                else:
                    if printed:
                        st.success(f"Saved and printed. {message}")
                    else:
                        st.warning(f"Saved, but printing failed: {message}")
        with save_col:
            if st.button("Save Only (No Print)"):
                try:
                    save_issuance(data, qr_string)
                except Exception as error:
                    st.error(f"Could not save asset record: {error}")
                else:
                    st.success("Asset saved successfully.")

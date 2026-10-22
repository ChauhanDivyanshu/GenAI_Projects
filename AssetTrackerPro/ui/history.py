"""View, edit, re-print, or soft-delete asset records."""

import json

import streamlit as st

from core.database import (
    get_all_issuances,
    search_issuances,
    update_issuance,
    delete_issuance,
)
from core.qr_generator import build_qr_payload, generate_qr_image
from core.printer_service import print_asset_label


ASSET_STATUSES = ("Issued", "Available", "In Repair", "Retired", "Lost")


def _asset_data(record):
    return {
        "asset_id": record.get("asset_id") or record.get("emp_id", ""),
        "asset_name": record.get("asset_name") or record.get("model", ""),
        "asset_code": record.get("asset_code") or record.get("serial_number", ""),
        "issue_date": record.get("issue_date") or "",
        "issuer_name": record.get("issuer_name") or record.get("issued_by", ""),
        "issued_to": record.get("issued_to") or record.get("emp_name", ""),
        "department": record.get("department") or "",
        "location": record.get("location") or "",
        "status": record.get("asset_status") or "Issued",
        "mac_address": record.get("mac_address") or "",
        "ip_address": record.get("ip_address") or "",
        "hardware_id": record.get("hardware_id") or "",
        "hostname": record.get("hostname") or "",
        "model": record.get("model") or "",
        "serial_number": record.get("serial_number") or "",
        "os": record.get("os") or "",
        "manufacturer": record.get("manufacturer") or "",
    }


def render():
    st.header("Issuance History")

    search = st.text_input("Search (asset / person / code / system detail)", "")
    records = search_issuances(search) if search else get_all_issuances()
    st.caption(f"Showing {len(records)} records")

    if not records:
        st.info("No records yet.")
        return

    for rec in records:
        data = _asset_data(rec)
        with st.expander(
            f"#{rec['id']} | {data['asset_name']} ({data['asset_code']}) | "
            f"{data['issued_to']} | {data['issue_date']} | [{data['status']}]"
        ):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**Asset ID:** {data['asset_id']}")
                st.write(f"**Issuer:** {data['issuer_name']}")
                st.write(f"**Department:** {data['department']}")
                st.write(f"**Location:** {data['location']}")
                st.write(f"**MAC:** {data['mac_address']}")
                st.write(f"**IP:** {data['ip_address']}")
                st.write(f"**Hardware ID:** {data['hardware_id']}")
                st.write(f"**Hostname:** {data['hostname']}")
                st.write(f"**Model:** {data['model']}")
                st.write(f"**Serial:** {data['serial_number']}")
                st.write(f"**OS:** {data['os']}")
                st.write(f"**Created:** {rec['created_at']}")
                st.write(f"**Updated:** {rec['updated_at']}")
            with c2:
                payload = build_qr_payload(data)
                qr_img = generate_qr_image(payload, box_size=5)
                st.image(qr_img, width=180)

            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Edit", key=f"edit_{rec['id']}"):
                    st.session_state[f"editing_{rec['id']}"] = True
            with b2:
                if st.button("Re-Print", key=f"print_{rec['id']}"):
                    qr_payload = json.dumps(
                        payload, separators=(",", ":"), ensure_ascii=False
                    )
                    ok, msg = print_asset_label(
                        qr_payload,
                        data["asset_name"],
                        data["asset_id"] or data["asset_code"],
                    )
                    if ok:
                        st.success(f"Sent to printer. {msg}")
                    else:
                        st.error(msg)
            with b3:
                if st.button("Delete", key=f"del_{rec['id']}"):
                    delete_issuance(rec["id"])
                    st.rerun()

            if st.session_state.get(f"editing_{rec['id']}", False):
                st.markdown("##### Edit Record")
                with st.form(f"edit_form_{rec['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        asset_id = st.text_input("Asset ID", value=data["asset_id"])
                        asset_name = st.text_input(
                            "Asset Name *", value=data["asset_name"]
                        )
                        asset_code = st.text_input(
                            "Asset Code *", value=data["asset_code"]
                        )
                        issue_date = st.text_input(
                            "Issue Date", value=data["issue_date"]
                        )
                        issuer_name = st.text_input(
                            "Issuer Name", value=data["issuer_name"]
                        )
                        issued_to = st.text_input(
                            "Issued To", value=data["issued_to"]
                        )
                        department = st.text_input(
                            "Department", value=data["department"]
                        )
                        location = st.text_input("Location", value=data["location"])
                    with col2:
                        status_options = list(ASSET_STATUSES)
                        if data["status"] not in status_options:
                            status_options.append(data["status"])
                        status = st.selectbox(
                            "Asset Status",
                            status_options,
                            index=status_options.index(data["status"]),
                        )
                        mac = st.text_input("MAC Address", value=data["mac_address"])
                        ip = st.text_input("IP Address", value=data["ip_address"])
                        hardware_id = st.text_input(
                            "Hardware ID", value=data["hardware_id"]
                        )
                        hostname = st.text_input("Hostname", value=data["hostname"])
                        model = st.text_input("Model", value=data["model"])
                        serial = st.text_input(
                            "Serial Number", value=data["serial_number"]
                        )
                        os_val = st.text_input("Operating System", value=data["os"])
                        manufacturer = st.text_input(
                            "Manufacturer", value=data["manufacturer"]
                        )

                    if st.form_submit_button("Save Changes"):
                        if not asset_name.strip() or not asset_code.strip():
                            st.error("Asset Name and Asset Code are required.")
                            return
                        new_data = {
                            "asset_id": asset_id.strip(),
                            "asset_name": asset_name.strip(),
                            "asset_code": asset_code.strip(),
                            "issuer_name": issuer_name.strip(),
                            "issued_to": issued_to.strip(),
                            "department": department.strip(),
                            "location": location.strip(),
                            "status": status,
                            "issue_date": issue_date.strip(),
                            "hostname": hostname,
                            "model": model.strip(),
                            "serial_number": serial.strip(),
                            "mac_address": mac.strip(),
                            "ip_address": ip.strip(),
                            "hardware_id": hardware_id.strip(),
                            "os": os_val,
                            "manufacturer": manufacturer.strip(),
                        }
                        new_payload = build_qr_payload(new_data)
                        qr_payload = json.dumps(
                            new_payload,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                        update_issuance(rec["id"], new_data, qr_payload)
                        st.session_state[f"editing_{rec['id']}"] = False
                        st.success("Updated. New QR regenerated.")
                        st.rerun()

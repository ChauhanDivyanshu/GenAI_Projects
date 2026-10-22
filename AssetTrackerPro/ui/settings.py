import json

import streamlit as st
from core.printer_service import (
    check_printer_status,
    launch_zm_service,
    load_config,
    print_asset_label,
    save_config,
)

LABEL_SIZE_PRESETS = {
    "4.4 × 4.5 cm — measured current roll (44 × 45 mm)": (44, 45),
    "4 × 3 in (101.6 × 76.2 mm)": (101.6, 76.2),
    "4 × 2 in (101.6 × 50.8 mm)": (101.6, 50.8),
    "3 × 2 in (76.2 × 50.8 mm)": (76.2, 50.8),
    "2 × 1 in (50.8 × 25.4 mm)": (50.8, 25.4),
    "Custom size": None,
}


def _get_size_preset(cfg):
    configured_size = (float(cfg["label_width_mm"]), float(cfg["label_height_mm"]))
    for name, size in LABEL_SIZE_PRESETS.items():
        if size and all(abs(actual - expected) < 0.2 for actual, expected in zip(configured_size, size)):
            return name
    return "Custom size"


def render():
    st.title("Settings & QR Printer")

    cfg = load_config()
    status = check_printer_status()

    st.subheader("ZMPrintService Status")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**WebSocket Service:**")
        if status["ws_online"]:
            st.success(f"ONLINE ({status['ws_url']})")
        else:
            st.error(f"OFFLINE ({status['ws_url']})")

    with col2:
        st.write("**Windows Process:**")
        if status["process_active"]:
            st.success("RUNNING")
        else:
            st.warning("STOPPED")

    with col3:
        st.write("**Print Mode:**")
        st.info(status["protocol"])

    if st.button("Start ZMPrintService"):
        ok, message = launch_zm_service()
        if ok:
            st.success(message)
        else:
            st.error(message)
        st.rerun()

    if st.button("Print QR Alignment Test"):
        test_payload = json.dumps(
            {
                "asset_id": "TEST001",
                "asset_name": "Alignment Test",
                "asset_code": "TEST-001",
                "issue_date": "2026-01-01",
                "issuer_name": "AssetTrackerPro",
                "issued_to": "Printer Test",
                "status": "Test",
            },
            separators=(",", ":"),
        )
        ok, message = print_asset_label(
            test_payload, "Alignment Test", "TEST-0001"
        )
        if ok:
            st.success(message)
        else:
            st.error(message)

    st.divider()
    st.subheader("QR Label Configuration")

    with st.form("settings_form"):
        zm_path = st.text_input(
            "ZMPrintService.exe path (leave blank when bundled with the app)",
            cfg.get("zm_service_path", ""),
        )
        ws_host = st.text_input("Service host", cfg["ws_host"])
        ws_port = st.number_input(
            "Service port", min_value=1, max_value=65535, value=int(cfg["ws_port"])
        )

        size_choice = st.selectbox(
            "Label/tag size",
            list(LABEL_SIZE_PRESETS),
            index=list(LABEL_SIZE_PRESETS).index(_get_size_preset(cfg)),
            help="Choose the physical size of one label. Current roll was measured at about 44 × 45 mm.",
        )
        selected_size = LABEL_SIZE_PRESETS[size_choice]
        if selected_size is None:
            st.info("Enter the width and height of one label in millimeters.")
            custom_col1, custom_col2 = st.columns(2)
            with custom_col1:
                label_width_mm = st.number_input(
                    "Label width (mm)",
                    min_value=10.0,
                    max_value=250.0,
                    value=float(cfg["label_width_mm"]),
                    step=0.5,
                )
            with custom_col2:
                label_height_mm = st.number_input(
                    "Label length (mm)",
                    min_value=10.0,
                    max_value=250.0,
                    value=float(cfg["label_height_mm"]),
                    step=0.5,
                )
        else:
            label_width_mm, label_height_mm = selected_size
            st.caption(
                f"Selected tag: {label_width_mm:g} × {label_height_mm:g} mm"
            )

        col1, col2, col3 = st.columns(3)
        with col1:
            dpi = st.number_input(
                "Printer DPI",
                min_value=100,
                max_value=1200,
                value=int(cfg["dpi"]),
                help="Use the DPI printed on the printer label/specification. The previous app setting was 203 DPI.",
            )
        with col2:
            label_gap = st.number_input(
                "Label gap (mm)",
                min_value=0.0,
                max_value=20.0,
                value=float(cfg["label_gap_mm"]),
                step=0.5,
            )
        with col3:
            print_speed = st.number_input(
                "Print speed (2-8)",
                min_value=2,
                max_value=8,
                value=int(cfg["print_speed"]),
                help="For stronger, more consistent thermal output, start with speed 2.",
            )
            print_darkness = st.number_input(
                "Print darkness (0-20)",
                min_value=0,
                max_value=20,
                value=int(cfg["print_darkness"]),
                help="Default is 14. Increase gradually if the QR prints pale; stop if bars fill in.",
            )

        qr_module_size = st.number_input(
            "QR module size",
            min_value=1,
            max_value=10,
            value=int(cfg["qr_module_size"]),
            help="Module size is measured in printer dots. Default 3 keeps the QR compact on the measured 44 × 45 mm tag.",
        )
        st.markdown("**Fine alignment (mm)**")
        offset_col1, offset_col2 = st.columns(2)
        with offset_col1:
            alignment_x = st.number_input(
                "Horizontal offset",
                min_value=-10.0,
                max_value=10.0,
                value=float(cfg["alignment_x_mm"]),
                step=0.5,
                help="Positive moves the whole label right; negative moves it left.",
            )
        with offset_col2:
            alignment_y = st.number_input(
                "Vertical offset",
                min_value=-10.0,
                max_value=10.0,
                value=float(cfg["alignment_y_mm"]),
                step=0.5,
                help="Positive moves the whole label down; negative moves it up.",
            )
        company_name = st.text_input(
            "Company name on label", cfg["company_name"]
        )
        default_issuer = st.text_input(
            "Default issued by", cfg["default_issuer"]
        )

        if st.form_submit_button("Save Settings"):
            cfg["zm_service_path"] = zm_path.strip()
            cfg["ws_host"] = ws_host.strip() or "127.0.0.1"
            cfg["ws_port"] = int(ws_port)
            cfg["dpi"] = int(dpi)
            cfg["label_width_mm"] = round(label_width_mm, 2)
            cfg["label_height_mm"] = round(label_height_mm, 2)
            cfg["label_gap_mm"] = label_gap
            cfg["print_speed"] = int(print_speed)
            cfg["print_darkness"] = int(print_darkness)
            cfg["qr_module_size"] = int(qr_module_size)
            cfg["alignment_x_mm"] = alignment_x
            cfg["alignment_y_mm"] = alignment_y
            cfg["company_name"] = company_name
            cfg["default_issuer"] = default_issuer
            save_config(cfg)
            st.success("QR printer settings saved.")
            st.rerun()

    st.caption(
        "AssetTrackerPro sends QR-label commands only. RFID read/write and encoding "
        "commands are not used."
    )
    st.caption(
        "Width is across the roll and length is along the roll movement. Label gap is "
        "the blank space between consecutive tags. Incorrect printer DPI can change the "
        "physical print size. Run printer media calibration after changing the roll."
    )
    st.caption("Save changed settings before printing the alignment test.")

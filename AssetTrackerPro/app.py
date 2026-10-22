import streamlit as st
from core.printer_service import launch_zm_service, load_config
from core.database import init_db
from ui import single_issue, bulk_issue, history, settings

# Page configuration
st.set_page_config(
    page_title="Infosware Asset Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database tables
init_db()

# Auto-launch USB Printer service on app start
if "zm_checked" not in st.session_state:
    st.session_state.zm_launch_result = launch_zm_service()
    st.session_state.zm_checked = True

def main():
    st.sidebar.title("Infosware Asset Tracker")
    st.sidebar.caption("Laptop issuance and QR printing")
    launch_result = st.session_state.get("zm_launch_result")
    if launch_result and not launch_result[0]:
        st.sidebar.warning(launch_result[1])

    page = st.sidebar.radio(
        "Navigate",
        ["Single Issue", "Bulk Issue", "History / Edit", "Settings"]
    )

    st.sidebar.divider()
    st.sidebar.info("Scan QR on C72 device to view embedded details. No internet required for scanning.")

    if page == "Single Issue":
        single_issue.render()
    elif page == "Bulk Issue":
        bulk_issue.render()
    elif page == "History / Edit":
        history.render()
    elif page == "Settings":
        settings.render()

if __name__ == "__main__":
    main()

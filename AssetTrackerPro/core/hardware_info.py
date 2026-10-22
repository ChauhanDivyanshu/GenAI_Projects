import socket
import platform
import uuid

def get_laptop_details():
    """Fetches local hardware details safely with WMI thread initialization."""
    details = {
        "hostname": socket.gethostname(),
        "model": "Unknown",
        "serial_number": "Unknown",
        "mac_address": "Unknown",
        "os": f"{platform.system()} {platform.release()}",
        "manufacturer": "Unknown"
    }

    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

    try:
        import wmi
        c = wmi.WMI()
        for sys in c.Win32_ComputerSystem():
            if sys.Model: details["model"] = str(sys.Model).strip()
            if sys.Manufacturer: details["manufacturer"] = str(sys.Manufacturer).strip()
        for bios in c.Win32_BIOS():
            if bios.SerialNumber: details["serial_number"] = str(bios.SerialNumber).strip()
        for nic in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
            if nic.MACAddress:
                details["mac_address"] = str(nic.MACAddress).replace(":", "-").strip()
                break
    except Exception as e:
        print(f"WMI Notice: {e}")

    if details["mac_address"] == "Unknown":
        try:
            mac = uuid.getnode()
            details["mac_address"] = '-'.join(['{:02x}'.format((mac >> elements) & 0xff) for elements in range(0,8*6,8)][::-1]).upper()
        except Exception:
            pass

    return details

get_local_hardware_details = get_laptop_details

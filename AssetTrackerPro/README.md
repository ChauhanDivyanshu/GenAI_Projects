# AssetTrackerPro

AssetTrackerPro records assets, generates offline QR payloads, and prints QR asset labels through the included `ZMPrintService`.

## Run

1. Install the packages from `requirements.txt`.
2. Keep `ZMPrintService.exe`, `ZMPCL.dll`, `ZMPrintService.exe.config`, and `ZMPrintService.ini` together in the AssetTrackerPro application folder.
3. Start `run_app.bat`. AssetTrackerPro starts the print service when it is not already listening.
4. In **Settings**, confirm the service status and set the printer DPI and physical label width, height, and gap to match the media loaded in the printer.
5. Use **Single Asset** or **Bulk Asset Issue** to enter asset details, save records, and print QR labels. Existing labels can be edited or reprinted from **History / Edit**.

The QR code contains the full-name JSON fields `asset_id`, `asset_name`, `asset_code`, `issue_date`, `issuer_name`, `issued_to`, `department`, `location`, and `status`. MAC address, IP address, hardware ID, hostname, model, serial number, operating system, and manufacturer are optional and are only included when manually provided. Bulk import accepts CSV or Excel files; `asset_name` and `asset_code` are required. The CSV template is in `templates/bulk_template.csv`.

The current roll label was measured at approximately **44 x 45 mm**. That is the default label size; the previous 101.6 x 101.6 mm default is automatically replaced when loading the old default configuration. Printer DPI remains 203 until confirmed from the printer specification; select the actual DPI in Settings because an incorrect value changes physical size. Settings includes other label presets and a custom-size option in millimeters. The label gap is configured separately. The QR is centered below a short header to avoid overflowing the small tag; its QR modules default to 3 printer dots. Fine X/Y offsets are available for printer-specific alignment. Save settings, calibrate the printer after changing the roll, then use **Print QR Alignment Test** before issuing assets. The ZM service must be configured to listen on the same host and port shown in Settings (default: `127.0.0.1:1808`).

Thermal print darkness and alignment depend on the printer, media, printhead, and DPI. If the test is still pale, increase darkness one step at a time; if QR squares start merging, lower it again. Confirm the printer DPI and run its media calibration before adjusting alignment offsets.

The current printer integration is QR-only. It does not issue RFID read, write, or encode commands. Network RAW/ZPL and PCLE printing are not used. For consistent placement, load the label roll straight and run the printer's media calibration before the first print; AssetTrackerPro checks QR/text bounds and will refuse settings that place them outside the label.

## Build the Windows app

Run `build_exe.bat` from this directory. The PyInstaller bundle includes the ZMPrintService executable and its required companion files.

## Tests

Run `python -m unittest discover -s tests` from this directory.

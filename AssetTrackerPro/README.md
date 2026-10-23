# AssetTrackerPro

AssetTrackerPro records assets, generates offline QR payloads, and prints QR asset labels through the included `ZMPrintService`.

## Run

1. Install the packages from `requirements.txt`.
2. Keep `ZMPrintService.exe`, `ZMPCL.dll`, `ZMPrintService.exe.config`, and `ZMPrintService.ini` together in the AssetTrackerPro application folder.
3. Start `run_app.bat`. AssetTrackerPro starts the print service when it is not already listening.
4. In **Settings**, confirm the service status and set the printer DPI and physical label width, height, and gap to match the media loaded in the printer.
5. Use **Single Asset** or **Bulk Asset Issue** to enter asset details, save records, and print QR labels. Existing labels can be edited or reprinted from **History / Edit**.

The QR code contains the full-name JSON fields `asset_id`, `asset_name`, `asset_code`, `issue_date`, `issuer_name`, `issued_to`, `department`, `location`, and `status`. MAC address, IP address, hardware ID, hostname, model, serial number, operating system, and manufacturer are optional and are only included when manually provided. Printed labels include the asset name/code and a readable `Asset ID` next to the QR. Bulk import accepts CSV or Excel files; `asset_name` and `asset_code` are required. Download either template from **Bulk Asset Issue**.

Settings includes label sizes used for testing (including **100 x 25 mm**) and a custom-size option in millimeters. Width is across the roll and length is along the feed direction. Match the configured dimensions and DPI to the physical labels and printer specification before printing. Wide labels place the QR beside the centered text; compact labels place the QR between the title and ID. The QR module size is reduced when required to fit while retaining at least 2 printer dots per module. Fine X/Y offsets are available for printer-specific alignment. Save settings, calibrate the printer after changing the roll, then use **Print QR Alignment Test** before issuing assets. The ZM service must be configured to listen on the same host and port shown in Settings (default: `127.0.0.1:1808`).

Thermal print darkness and alignment depend on the printer, media, printhead, and DPI. If the test is still pale, increase darkness one step at a time; if QR squares start merging, lower it again. Confirm printer DPI and actual label gap, and run the printer's media calibration before adjusting alignment offsets. A gap near zero may require the printer's continuous-media or mark-sensing mode rather than ordinary gap sensing.

The current printer integration is QR-only. It does not issue RFID read, write, or encode commands. Network RAW/ZPL and PCLE printing are not used. Bulk printing waits between labels and checks that the printer is ready. If the printer pauses, press its Pause button; the current label is retried after the printer reports ready, and labels already confirmed are not resent. If the printer does not resume within two minutes or reports a media/ribbon/USB error, the batch stops and reports the remaining labels. For consistent placement, load the label roll straight and run the printer's media calibration before the first print; AssetTrackerPro checks QR/text bounds and will refuse settings that place them outside the label.

## Build the Windows app

Run `build_exe.bat` from this directory. The PyInstaller bundle includes the ZMPrintService executable and its required companion files.

## Tests

Run `python -m unittest discover -s tests` from this directory.

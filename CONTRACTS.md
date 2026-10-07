# Contracts between the three owners

One codebase, three owners. The UI and the data layer depend **only** on the two Protocols
below (`src/parkomate/core/interfaces.py`), never on an implementation. Aditya and Piyush can
replace the stand-ins without touching UI or data code.

| Owner | Implements | Lives in | Stand-in used today |
|---|---|---|---|
| Aditya | `HardwareService` | `src/parkomate/hardware/` | `hardware/mocks/MockHardwareService` |
| Piyush | `WorkflowService` | `src/parkomate/workflow/` | `workflow/stub/StubWorkflowService` |
| Yugant | records API, reports, mail, auth, settings, logs, i18n, UI | everything else | - |

Shared types live in `src/parkomate/core/`: `models.py` (pydantic, frozen), `enums.py`
(`Stage`, `CheckCode`, ...), `errors.py` (`ParkomateError` + `ErrorCode`), `events.py`
(`EventBus` + event classes).

> Changes against the list in the build prompt are recorded at the top of `DECISIONS.md`.

---

## 1. HardwareService (Aditya)

Everything that touches the bench: serial port, ESP32, server API, measurement device, camera.

```python
list_ports() -> list[PortInfo]          # known ESP32 bridges first (is_esp_candidate)
connect(port: str) -> None              # HW_NO_PORT / HW_PORT_BUSY
disconnect() -> None                    # safe when not connected; next connect = next board
is_connected() -> bool
read_mac() -> str                       # "AA:BB:CC:DD:EE:FF"
chip_name() -> str                      # "ESP32-D0WD-V3 (revision v3.1)" or ""
check_whitelist(mac) -> WhitelistResult # allowed=False is a normal result, not an exception
fetch_firmware() -> FirmwareInfo        # download into RAM, verify SHA-256
firmware_info() -> FirmwareInfo | None  # metadata of the image held in RAM
flash(progress_cb) -> FlashResult       # progress 0..100; lost port -> HW_COM_DISCONNECTED
ping() -> bool
read_sensor() -> SensorReading
get_device_id() -> str                  # "" when the board has no ID
set_device_id(device_id) -> bool        # True = board acknowledged
measure(timeout_s) -> Measurement       # MEAS_TIMEOUT / MEAS_BAD_DATA
measure_ambient() -> float              # °C
open_camera() / close_camera()
read_qr(timeout_s) -> str | None        # None = nothing readable in time
get_preview_frame() -> PreviewFrame | None   # RGB888; must return immediately (UI polls ~15 fps)
shutdown() -> None                      # release everything, ZERO the firmware buffer
```

Rules
* **Threading** - every method except `get_preview_frame` may block; the UI calls them from
  one worker thread (`TaskRunner(1)`), so calls never overlap. They must not touch Qt.
* **Errors** - every failure raises a `ParkomateError` subclass (`HardwareError`,
  `ServerError`, `MeasurementError`, `CameraError`) with a specific `ErrorCode`. The UI turns
  the code into title / cause / numbered fix steps from the catalogue (`error.<code>.*`).
  Never raise a bare exception; never put user text in the exception.
* **Firmware** - kept in a `bytearray` only, never written to disk, temp files, logs or
  reports; zeroed by `shutdown()`. (Integration test scans the data folder for it.)
* **Boards** - a `connect()` after `disconnect()` is a new board. A lost port during flashing
  (`HW_COM_DISCONNECTED`) keeps the same board: the operator re-plugs and retries.

## 2. WorkflowService (Piyush)

The brain: stage order, stage gates, limit checks, reject / retry / complete. It records every
result through `ProductionRecords` (Yugant) and publishes events on the shared `EventBus`.

```python
start_device(mac) -> DeviceState                      # new device at PROGRAMMING
current_device() -> DeviceState | None                # None = bench idle
current_stage() -> Stage                              # PROGRAMMING when idle
abandon_device() -> None                              # session ends with a board on the bench
clear_finished() -> None                              # forget a completed/rejected device
required_checks(stage) -> list[CheckCode]
missing_checks() -> list[CheckCode]                   # drives "Still needed: ..." and gates
is_stage_complete(stage) -> bool
submit_check(code, value=None, *, text=None) -> CheckOutcome
can_submit() -> bool
submit_and_next() -> Stage                            # COMPLETE after packaging
reject(code, reason_key="reject.reason.manual", **params) -> RejectInstruction
can_retry_programming() -> bool
evaluate_measurement(Measurement) -> list[CheckOutcome]
reconcile_identity(qr_id, device_id, *, after_write=False, method=CAMERA) -> IdentityOutcome
```

`submit_check` values: `bool` for automatic / operator-marked checks (whitelist allowed,
upload success, ping ok, sensor OK, indicator OK, checklist ticked), `float` for sensor
readings (`B2_READING_n`, strictly in order), `str` for the decoded QR (`C_QR_READ`). `text`
is optional detail (firmware version on upload success, error code on failure, whitelist
reason). Electrical checks go only through `evaluate_measurement`, identity only through
`reconcile_identity`.

**Final failures reject inside the call.** When a failure is not retriable the service calls
`ProductionRecords.reject_device(...)`, publishes `DeviceRejected` and returns the outcome with
`.reject` set. Retriable failures return `retry_allowed=True` (today: firmware upload, up to
`programming.max_retries` attempts).

**Identity protocol** (UI does the I/O, workflow decides):
1. UI reads the board ID, calls `reconcile_identity(qr, board_id)`
   → `MATCH` (done) or `WRITE_REQUIRED`.
2. On `WRITE_REQUIRED` the UI calls `set_device_id(qr)` then `get_device_id()` and calls
   `reconcile_identity(qr, readback, after_write=True)` → `CONFIRMED` or `FAILED` (rejected).
   A refused write is reported as `readback=None`.

**Events** (`core/events.py`): `DeviceStarted`, `StageChanged`, `CheckRecorded`,
`DeviceCompleted`, `DeviceRejected`. The UI listens through `EventBridge` (queued to the GUI
thread); it shows the reject takeover on `DeviceRejected` and the success toast on
`DeviceCompleted`, whichever call caused them.

Threading: workflow methods are quick (SQLite writes) and are called from the GUI thread.

## 3. What Yugant provides to both

* `ProductionRecords` (`data/records.py`) - session/device/check/counter persistence with state
  validation (`start_device`, `record_check`, `set_device_id`, `complete_device`,
  `reject_device`, `counter_event`, `can_adjust_failure`, `record_ambient`, ...).
* `Settings` (`config/settings.py`) - typed limits, timeouts, server, measurement, camera.
* `EventBus`, `ParkomateError` + i18n keys for every `ErrorCode`.
* Translations: any new user-facing text needs a key in **both** `i18n/en.json` and
  `i18n/mr.json` (a test fails otherwise).

## 4. Typical sequence (one passing device)

```
UI (worker)   hw.list_ports → hw.connect → hw.read_mac
UI            wf.start_device(mac)
UI (worker)   hw.check_whitelist(mac)        → wf.submit_check(A_WHITELIST, allowed)
UI (worker)   hw.flash(progress)             → wf.submit_check(A_UPLOAD, ok, text=version)
UI            wf.submit_and_next()           → TESTING
UI (worker)   hw.ping()                      → wf.submit_check(B1_COMM, ok)
UI (worker)   hw.read_sensor() ×N            → wf.submit_check(B2_READING_n, value)
operator      ✓ / ✕                          → wf.submit_check(B2_SENSOR_OK / B2_INDICATOR_OK, ok)
UI (worker)   hw.measure(timeout)            → wf.evaluate_measurement(m)
UI            wf.submit_and_next()           → LABELING
UI (worker)   hw.open_camera, hw.read_qr     → wf.submit_check(C_QR_READ, qr)
UI (worker)   hw.get_device_id               → wf.reconcile_identity(qr, id) [→ write/readback]
operator      F1–F4                          → wf.submit_check(C1..C4, True)
UI            wf.submit_and_next()           → PACKAGING → D1..D4 → COMPLETE
```

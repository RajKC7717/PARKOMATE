# Decisions and assumptions

Every default chosen without an explicit instruction, and why. Items marked **(client)** are
also listed as open questions in the last section.

## Contract changes (read first - Aditya and Piyush)

Relative to the interface list in the build prompt:

**HardwareService - added**
* `is_connected()`, `chip_name()` - the UI shows the chip in step 1 and must know whether to
  reconnect before a retry.
* `firmware_info()` - metadata of the image already in RAM (session start loads it once).
* `get_preview_frame() -> PreviewFrame | None` - camera preview for the UI (RGB888, polled
  ~15 fps, must not block). The mock returns `None`; the UI then draws a placeholder.
* `disconnect()` semantics: the next `connect()` is a new board.

**WorkflowService - added / made explicit**
* `start_device(mac)`, `abandon_device()`, `clear_finished()`, `missing_checks()`.
* `current_device()` returns `None` when the bench is idle.
* `submit_check(code, value=None, *, text=None)` - one signature for bool / float / str
  values plus optional detail text.
* `reject(code, reason_key="reject.reason.manual", **params)` - reason is an i18n key + params.
* `reconcile_identity(qr, device_id, *, after_write=False, method=CAMERA)` - two-step
  protocol (decide → UI writes/reads back → confirm); the UI performs the hardware I/O.
* Final (non-retriable) failures reject inside the call and return `outcome.reject`.

**Shared types - added**
* `CheckCode.B2_READING_6..10` (reading count configurable up to 10) and `CheckCode.B3_T_AMB`
  (ambient reported by the measuring device, stored for traceability, no pass/fail).
* Error codes beyond the prompt's list: `HW_NO_PORT`, `HW_PORT_BUSY`, `HW_TIMEOUT`,
  `HW_DEVICE_ERROR`, `HW_FLASH_FAILED`, `HW_HOLD_BOOT`, `API_BAD_RESPONSE`, `FW_NOT_LOADED`,
  `QR_BAD_FORMAT`, `MAIL_NOT_CONFIGURED`, `SETTINGS_INVALID`, `SECRET_MISSING`,
  `REPORT_FAILED`, `AUTH_*`, `PERMISSION_DENIED`, `INVALID_STATE`, `INVALID_INPUT`,
  `NOT_FOUND`, `ALREADY_RUNNING`, `UNEXPECTED`.

**Database - extra columns** (beyond the prompt's table list)
* `devices.reject_reason_key`, `devices.reject_reason_params` - the reason is stored as an
  i18n key + parameters so reports can render it in either language; `reject_reason` keeps
  an English rendering for direct SQL reads.
* `operators.language` - language remembered per operator.
* `email_outbox.subject`, `email_outbox.next_attempt_at` - outbox list and retry back-off.
* Triggers make `audit_log`, `counter_events` and `check_results` append-only.

## Tooling

| # | Decision | Why |
|---|---|---|
| T1 | **uv** + `pyproject.toml`, Python pinned to 3.12 (`>=3.12,<3.13`), `uv.lock` committed | fast, reproducible; uv also installs Python 3.12 itself |
| T2 | hatchling build backend, `src/` layout | standard; package data (SQL, JSON, fonts) ships automatically |
| T3 | mypy **strict on the whole package** (core, data, config, auth, reports, mail *and* UI) | stricter than required; caught a real `QWidget.render` override |
| T4 | ruff with bugbear, bandit (`S`), pathlib, naming; `S105` and SQL `S608` (repositories only) ignored with written reasons | enum names like `ALL_PASS` trip S105; SQL is built only from module-constant column lists |
| T5 | git was **not initialised** in the folder, so no commits were made | the prompt says "if git is initialised"; commit is your call |

## Data and records

| # | Decision | Why |
|---|---|---|
| D1 | Data folder `%PROGRAMDATA%\Parkomate` (Windows), `~/.parkomate` elsewhere, override `PARKOMATE_DATA_DIR`; settings override `PARKOMATE_SETTINGS` | shared by all Windows users of the bench PC. **The installer (full build) must give the Users group modify rights on that folder.** |
| D2 | Timestamps stored as UTC ISO-8601 with microseconds (`…+00:00`), shown/reported in local time with offset | sortable as text, unambiguous |
| D3 | One SQLite connection guarded by a re-entrant lock; nested `transaction()` = SAVEPOINT; every `sqlite3.Error` → `DatabaseError` | GUI thread and workers share it safely; inner failures roll back only their own work |
| D4 | WAL + `synchronous=NORMAL` | survives app crashes; a power cut can lose at most the last transaction |
| D5 | Migration runner backs up the DB (`backups/`) before upgrading an existing schema; refuses a DB newer than the app | safe upgrades in the field |
| D6 | `Stage` values are names (`programming`…), with `.letter` A–D for boxes and reports; terminal `complete` / `rejected` | readable in SQL and logs |
| D7 | One device in progress per session, enforced in code **and** by a unique partial index | matches "one device at a time" |
| D8 | MAC addresses normalised to `AA:BB:CC:DD:EE:FF` | consistent search and reports |
| D9 | Counter **reset** (admin only) restarts the *live* counters; the session summary and reports always cover the whole session | history stays auditable |
| D10 | "Reduce failure count by 1": only after a failure *followed by* a success on the same device, once per device (unique index + check), audited | prompt rule |
| D11 | **First-pass yield** = completed devices with no upload failure ÷ devices that finished (complete + rejected); abandoned / in-progress excluded; shown as "-" when none finished **(client)** | common FPY definition |
| D12 | Crash recovery closes stale sessions at their **last recorded activity** (not "now"), marks in-progress devices `abandoned`, queues the report, and the login screen tells the operator | accurate times; operator knows to set the board aside |
| D13 | Retention purge deletes only payload files of **sent** e-mails older than `retention_days` (default 90); rows kept | prompt rule |

## Workflow stub (Piyush replaces it)

| # | Decision | Why |
|---|---|---|
| W1 | Only firmware upload is retriable (`programming.max_retries`, default 3 attempts in total) | P3 says "only programming is retriable by default" |
| W2 | A flash interrupted by an exception (cable pulled) **counts as a failed attempt** | the attempt happened; prevents endless retries |
| W3 | Communication test returning "no answer" rejects at B; a hardware *error* while pinging only shows the banner with "Test again" **(client)** | device fault vs. bench problem |
| W4 | QR unreadable / wrong format is *not* a device fault: banner + "Scan again", nothing rejected | the sticker or the angle is the problem |
| W5 | Values are rounded **half-up on their decimal representation** to `limits.decimals` (default 2) before the inclusive comparison, so 3.245 V → 3.25 V → pass, 3.2449 → 3.24 → fail **(client)** | avoids binary-float surprises; matches the 2-decimal limits |
| W6 | Regulator check: `round(T_reg − ambient) ≤ temp_margin_c`, using the **latest** ambient (session start or re-measure); stored with `limit_high = ambient + margin` | prompt rule + "Re-measure ambient" |
| W7 | Testing order enforced: B1 before readings; exactly N readings in order; sensor/indicator marks before measuring; measurement starts automatically when both are OK | gates exactly as specified |
| W8 | Checklist ticks can be unticked; they are written to the database when the stage is submitted | no false "pass" rows for accidental taps |
| W9 | Manual reject in Programming/Testing is attributed to the stage's first missing check; in Labeling/Packaging the operator chooses the failing item | always a concrete check code |

## E-mail, reports, logs, secrets

| # | Decision | Why |
|---|---|---|
| M1 | The complete MIME message is written to `outbox/*.eml` and the row inserted **before** any send; sending happens in the background | never lose a report |
| M2 | Recipients and sender are taken from the **current** settings at send time | fixing an address + "Resend" works |
| M3 | Back-off `retry_base_s · 2^(attempt-1)` capped at `retry_max_s`; after `max_attempts` → `failed` (admin "Resend"); pending items retried at start-up and every 5 minutes | prompt rule |
| M4 | E-mail disabled (default) → report files are still written to `reports/`, no outbox row | nothing to send |
| M5 | `security="none"` = internal relay **without** authentication: a password is never sent unencrypted | safety |
| M6 | OAuth2: SMTP XOAUTH2 transport implemented; token acquisition is a documented placeholder reading a token from the keyring (TODO: MSAL client-credentials before Microsoft disables basic auth end of Dec 2026) **(client)** | prompt asks for a pluggable placeholder |
| M7 | Secrets in the OS keyring under service `ParkomateStation`; settings hold only entry names (`*_ref`); unknown keys such as `email.password` are rejected with a hint | no secret can land in the TOML file |
| M8 | Report language `reports.language` (default `en`), independent of the UI language; sheet names and headings come from the catalogue | e-mails go to management |
| M9 | CSV = one file per sheet (`…_summary.csv`, `_devices.csv`, `_checks.csv`, `_rejections.csv`), UTF-8 **with BOM** | CSV holds one table; BOM makes Excel read Marathi |
| M10 | Spreadsheet formula injection neutralised (text starting with `= + - @` stored as text / prefixed with `'`) | a crafted QR code must not become a formula |
| M11 | Summary sheet is transposed (one column per session) so the same layout serves one session and a date range | one layout to confirm with the client |
| M12 | `errors.jsonl` receives ERROR and above; a logging filter redacts password/token/key values and replaces any bytes with `<N bytes>` | "never log secrets or firmware bytes" |
| M13 | Attachment MIME types are fixed for `.xlsx` / `.csv` | Windows maps `.csv` to `application/vnd.ms-excel` |

## Auth

| # | Decision | Why |
|---|---|---|
| A1 | Argon2id (argon2-cffi defaults), automatic re-hash on login when parameters change | current best practice |
| A2 | Unknown operator code and wrong password give the same message; unknown codes still cost one hash | no account or timing probing |
| A3 | Lock after 5 wrong passwords for 5 minutes (configurable); while locked the password is not checked; after expiry the operator gets a fresh set of attempts | prompt rule |
| A4 | "Account switched off" is only revealed after a correct password | no probing |
| A5 | The last active admin cannot be deactivated or demoted; admins cannot deactivate themselves | never lock the station out |
| A6 | `python -m parkomate admin create` only when no active admin exists; `admin unlock` / `admin reset-password` exist for recovery | first-run + lost-admin recovery |

## UI (Prompt 2)

| # | Decision | Why |
|---|---|---|
| U1 | PySide6 Widgets, MVVM: `views/` render, `viewmodels/` hold state and commands, `workers/TaskRunner` runs blocking work | prompt architecture |
| U2 | Hardware calls run on **one** worker thread (serialised); hashing/reports/e-mail on a second pool; results come back on the GUI thread via queued signals | never two hardware calls at once; UI never blocks (tested with a slow mock) |
| U3 | The bottom bar renders every stage the same way: status line, "why disabled" text, secondary buttons, **one primary button bottom-right**; Enter triggers it | principles 1, 5, 12 |
| U4 | Keys: Enter primary, Space toggles focused check row, F1–F4 checklist, F5 refresh ports, F9 re-measure ambient, Esc only cancels / closes (never ends, rejects or logs out) | principle 5 |
| U5 | After a device is completed or rejected the next board is **not** connected automatically; the port stays auto-selected and the operator presses Enter | a finished board still plugged in would otherwise be read again |
| U6 | Admin area is blocked while a device is in progress | no settings change mid-device |
| U7 | Bundled fonts: Noto Sans, Noto Sans Devanagari, Noto Sans Symbols 2 (✓ ✕), all OFL; font substitution registered so `·` and `°` render inside Marathi text | identical rendering on every PC |
| U8 | The global stylesheet sets **no font size** (the app font does), so `setFont()` on large elements works | the takeover text must be huge |
| U9 | Stage cards scroll instead of overlapping when content is taller than a 1366×768 screen (long Marathi text, error banner shown) | principle 15 |
| U10 | Status colours: dark green / dark red / amber on light tints, all ≥ 7:1 (AAA); focus ring amber ≥ 3:1; tested | principle 3 |
| U11 | Reject sound / complete sound = `QApplication.beep()` when `ui.sound` is on | no extra audio files |
| U12 | Manual ID entry (type twice) is **off** by default (`camera.allow_manual_entry`) and stored as `id_entry_method = manual` | prompt rule |
| U13 | Single instance per PC (`station.lock`); a second start shows an "Already running" screen | crash recovery assumes one process |
| U14 | Invalid settings show a full-page error naming each key (translated) instead of the station | "refuse start" |
| U15 | Settings saved from the admin screen are rewritten by `tomli-w`: comments are lost; a header points to `config/settings.example.toml`, which documents every key | TOML writers do not keep comments |
| U16 | Operator-marked failures and manual rejects ask for an inline confirmation in the bottom bar | gloved accidental taps; never an OS dialog |

## Mocks

| # | Decision | Why |
|---|---|---|
| K1 | Scenario from `PARKOMATE_MOCK_SCENARIO` (overrides `dev.mock_scenario`); hyphens or underscores accepted; unknown names stop the start-up | prompt rule |
| K2 | "Transient" scenarios fail only the first time per board (upload, measurement timeout, QR unreadable, cable pulled) so the recovery path is demonstrable; extra scenarios: `upload_always_fails`, `id_write_fails`, `comm_fail`, `camera_missing`, `mixed` | demos of every branch |
| K3 | `PARKOMATE_MOCK_DELAY` scales all delays (0 = instant, tests); `PARKOMATE_MOCK_SEED` makes runs repeatable | tests and demos |
| K4 | Mock sensor readings are distances in cm (142–158) **(client)** | sensor type not specified |

## Open questions for the client

1. **Measuring device**: transport (HTTP POST vs. MQTT), exact JSON fields and units, does it
   also report ambient, and which device measures the session-start ambient?
2. **Device link**: serial command set (`PING`, `READ_SENSOR`, `GET_ID`, `SET_ID`, `GET_MAC`?),
   baud rate, response format, does a fresh board have an ID at all?
3. **Server API**: base URL, authentication (token / mTLS), whitelist request and response,
   firmware response (single `.bin` or bootloader + partitions + app with offsets), where the
   SHA-256 comes from.
4. **Limits precision**: compare at 2 decimals with half-up rounding (W5)? Should 3.249 V pass?
5. **Retry policy**: may the communication test or the measurement be repeated after a
   failure, or is the first failure final (W1, W3)?
6. **First-pass yield** definition (D11).
7. **Report format**: required columns, Excel vs. CSV, recipients, language, one e-mail per
   session or one per shift/day?
8. **E-mail provider**: Microsoft 365 / Gmail? An OAuth app registration will be needed (M6).
9. **Device ID format** (regular expression for `camera.id_pattern`) and QR content.
10. **Duplicate boards**: what to do when a MAC or QR ID was already completed earlier.
11. Physical reject boxes labelled **A–D** per stage - confirm.
12. **Marathi texts**: native-speaker review (`src/parkomate/i18n/REVIEW.md`).
13. Retention period for sent e-mail files (90 days) and whether the database needs a
    scheduled backup / export to a server.

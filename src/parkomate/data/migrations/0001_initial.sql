-- 0001_initial: complete production schema.
-- All timestamps are ISO-8601 text in UTC with offset (e.g. 2026-10-06T08:15:02.123456+00:00).
-- Booleans are INTEGER 0/1. Enumerations are TEXT with CHECK constraints.

CREATE TABLE operators (
    id              INTEGER PRIMARY KEY,
    operator_code   TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    full_name       TEXT    NOT NULL,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('operator', 'admin')),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    locked_until    TEXT,
    language        TEXT,
    created_at      TEXT    NOT NULL
);

CREATE TABLE sessions (
    id                INTEGER PRIMARY KEY,
    operator_id       INTEGER NOT NULL REFERENCES operators (id),
    station_id        TEXT    NOT NULL,
    started_at        TEXT    NOT NULL,
    ended_at          TEXT,
    end_reason        TEXT CHECK (end_reason IN ('logout', 'close', 'crash_recovered')),
    firmware_name     TEXT,
    firmware_version  TEXT,
    firmware_sha256   TEXT,
    ambient_c_initial REAL,
    language          TEXT    NOT NULL,
    CHECK ((ended_at IS NULL) = (end_reason IS NULL))
);
CREATE INDEX ix_sessions_operator ON sessions (operator_id);
CREATE INDEX ix_sessions_started ON sessions (started_at);
CREATE INDEX ix_sessions_open ON sessions (id) WHERE ended_at IS NULL;

CREATE TABLE ambient_readings (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions (id),
    value_c     REAL    NOT NULL,
    measured_at TEXT    NOT NULL,
    reason      TEXT    NOT NULL CHECK (reason IN ('session_start', 'remeasure'))
);
CREATE INDEX ix_ambient_session ON ambient_readings (session_id, measured_at);

CREATE TABLE devices (
    id                   INTEGER PRIMARY KEY,
    session_id           INTEGER NOT NULL REFERENCES sessions (id),
    device_id            TEXT,
    mac_address          TEXT    NOT NULL,
    firmware_version     TEXT,
    started_at           TEXT    NOT NULL,
    finished_at          TEXT,
    status               TEXT    NOT NULL DEFAULT 'in_progress'
                         CHECK (status IN ('in_progress', 'complete', 'rejected', 'abandoned')),
    reject_stage         TEXT CHECK (reject_stage IN ('programming', 'testing', 'labeling', 'packaging')),
    reject_check_code    TEXT,
    reject_reason        TEXT,
    reject_reason_key    TEXT,
    reject_reason_params TEXT,
    programming_attempts INTEGER NOT NULL DEFAULT 0 CHECK (programming_attempts >= 0),
    id_entry_method      TEXT CHECK (id_entry_method IN ('camera', 'manual')),
    CHECK ((status = 'in_progress') = (finished_at IS NULL)),
    CHECK ((status = 'rejected') = (reject_stage IS NOT NULL)),
    CHECK ((status = 'rejected') = (reject_check_code IS NOT NULL))
);
CREATE INDEX ix_devices_session ON devices (session_id);
CREATE INDEX ix_devices_mac ON devices (mac_address);
CREATE INDEX ix_devices_device_id ON devices (device_id);
CREATE INDEX ix_devices_status ON devices (status);
-- One device on the bench at a time.
CREATE UNIQUE INDEX ux_devices_one_active ON devices (session_id) WHERE status = 'in_progress';

CREATE TABLE check_results (
    id              INTEGER PRIMARY KEY,
    device_row_id   INTEGER NOT NULL REFERENCES devices (id),
    stage           TEXT    NOT NULL CHECK (stage IN ('programming', 'testing', 'labeling', 'packaging')),
    check_code      TEXT    NOT NULL,
    value_text      TEXT,
    value_num       REAL,
    unit            TEXT,
    limit_low       REAL,
    limit_high      REAL,
    passed          INTEGER CHECK (passed IN (0, 1)),
    operator_marked INTEGER NOT NULL DEFAULT 0 CHECK (operator_marked IN (0, 1)),
    created_at      TEXT    NOT NULL
);
CREATE INDEX ix_checks_device ON check_results (device_row_id, id);
CREATE INDEX ix_checks_code ON check_results (check_code);

-- Counters are never stored as numbers: they are computed from these events.
CREATE TABLE counter_events (
    id            INTEGER PRIMARY KEY,
    session_id    INTEGER NOT NULL REFERENCES sessions (id),
    device_row_id INTEGER REFERENCES devices (id),
    event         TEXT    NOT NULL
                  CHECK (event IN ('upload_success', 'upload_failure', 'failure_adjusted', 'reset')),
    operator_id   INTEGER NOT NULL REFERENCES operators (id),
    created_at    TEXT    NOT NULL,
    CHECK (event = 'reset' OR device_row_id IS NOT NULL)
);
CREATE INDEX ix_counter_session ON counter_events (session_id, id);
CREATE INDEX ix_counter_device ON counter_events (device_row_id);
-- "Reduce failure count by 1" at most once per device.
CREATE UNIQUE INDEX ux_counter_adjust_once ON counter_events (device_row_id)
    WHERE event = 'failure_adjusted';

CREATE TABLE email_outbox (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER REFERENCES sessions (id),
    status          TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    attempts        INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error      TEXT,
    payload_path    TEXT,
    subject         TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL,
    sent_at         TEXT,
    next_attempt_at TEXT
);
CREATE INDEX ix_outbox_status ON email_outbox (status, next_attempt_at);

CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY,
    operator_id  INTEGER REFERENCES operators (id),
    action       TEXT    NOT NULL,
    details_json TEXT    NOT NULL DEFAULT '{}',
    created_at   TEXT    NOT NULL
);
CREATE INDEX ix_audit_created ON audit_log (created_at);
CREATE INDEX ix_audit_action ON audit_log (action);

-- History tables are append-only.
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER trg_audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER trg_counter_no_update BEFORE UPDATE ON counter_events
BEGIN SELECT RAISE(ABORT, 'counter_events is append-only'); END;
CREATE TRIGGER trg_counter_no_delete BEFORE DELETE ON counter_events
BEGIN SELECT RAISE(ABORT, 'counter_events is append-only'); END;
CREATE TRIGGER trg_checks_no_update BEFORE UPDATE ON check_results
BEGIN SELECT RAISE(ABORT, 'check_results is append-only'); END;
CREATE TRIGGER trg_checks_no_delete BEFORE DELETE ON check_results
BEGIN SELECT RAISE(ABORT, 'check_results is append-only'); END;

-- 0002_stage_transitions: every move of a device between stages (full build).
-- from_stage NULL = the device was started (entered PROGRAMMING).

CREATE TABLE stage_transitions (
    id            INTEGER PRIMARY KEY,
    device_row_id INTEGER NOT NULL REFERENCES devices (id),
    from_stage    TEXT CHECK (from_stage IN ('programming', 'testing', 'labeling', 'packaging')),
    to_stage      TEXT NOT NULL
                  CHECK (to_stage IN ('programming', 'testing', 'labeling', 'packaging',
                                      'complete', 'rejected')),
    created_at    TEXT NOT NULL
);
CREATE INDEX ix_transitions_device ON stage_transitions (device_row_id, id);

CREATE TRIGGER trg_transitions_no_update BEFORE UPDATE ON stage_transitions
BEGIN SELECT RAISE(ABORT, 'stage_transitions is append-only'); END;
CREATE TRIGGER trg_transitions_no_delete BEFORE DELETE ON stage_transitions
BEGIN SELECT RAISE(ABORT, 'stage_transitions is append-only'); END;

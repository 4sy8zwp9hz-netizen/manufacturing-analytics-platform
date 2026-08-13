PRAGMA foreign_keys = ON;

CREATE TABLE generation_metadata (
    generation_id TEXT PRIMARY KEY,
    refresh_started_at TEXT NOT NULL,
    refresh_completed_at TEXT,
    publication_status TEXT NOT NULL,
    warning_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE source_watermarks (
    source_name TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    watermark_value TEXT NOT NULL
);

CREATE TABLE canonical_wafers (
    canonical_wafer_id TEXT PRIMARY KEY,
    canonical_lot_id TEXT NOT NULL,
    canonical_work_order_id TEXT NOT NULL,
    product_code TEXT NOT NULL,
    analytical_period TEXT NOT NULL,
    completion_status TEXT NOT NULL,
    production_eligible INTEGER NOT NULL CHECK (production_eligible IN (0, 1))
);

CREATE TABLE stage_population (
    analytical_record_id TEXT PRIMARY KEY,
    canonical_wafer_id TEXT NOT NULL REFERENCES canonical_wafers(canonical_wafer_id),
    stage_code TEXT NOT NULL,
    population_unit TEXT NOT NULL,
    unit_key TEXT NOT NULL,
    is_denominator INTEGER NOT NULL CHECK (is_denominator IN (0, 1)),
    is_good INTEGER NOT NULL CHECK (is_good IN (0, 1)),
    failure_family TEXT,
    exclusion_reason TEXT,
    event_timestamp TEXT NOT NULL,
    x_coordinate INTEGER,
    y_coordinate INTEGER,
    UNIQUE (stage_code, unit_key)
);

CREATE TABLE analytical_lineage (
    lineage_id INTEGER PRIMARY KEY,
    analytical_record_id TEXT NOT NULL REFERENCES stage_population(analytical_record_id),
    source_system TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_record_key TEXT NOT NULL,
    reconciliation_method TEXT NOT NULL,
    transformation_note TEXT NOT NULL
);

CREATE TABLE transformation_issues (
    issue_id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_record_key TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    disposition TEXT NOT NULL,
    detail TEXT NOT NULL
);

CREATE INDEX idx_population_stage_period ON stage_population(stage_code, event_timestamp);
CREATE INDEX idx_population_wafer ON stage_population(canonical_wafer_id, stage_code);
CREATE INDEX idx_lineage_record ON analytical_lineage(analytical_record_id);

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id TEXT PRIMARY KEY,
    product_code TEXT NOT NULL,
    planned_quantity INTEGER NOT NULL CHECK (planned_quantity > 0),
    priority TEXT NOT NULL,
    release_timestamp TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lots (
    lot_id TEXT PRIMARY KEY,
    work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
    route_code TEXT NOT NULL,
    start_timestamp TEXT NOT NULL,
    completion_timestamp TEXT,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wafers (
    wafer_id TEXT PRIMARY KEY,
    lot_id TEXT NOT NULL REFERENCES lots(lot_id),
    wafer_number INTEGER NOT NULL CHECK (wafer_number > 0),
    diameter_mm INTEGER NOT NULL,
    status TEXT NOT NULL,
    UNIQUE (lot_id, wafer_number)
);

CREATE TABLE IF NOT EXISTS operations (
    operation_code TEXT PRIMARY KEY,
    operation_name TEXT NOT NULL,
    sequence_number INTEGER NOT NULL UNIQUE,
    tool_group TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tools (
    tool_id TEXT PRIMARY KEY,
    tool_group TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wafer_operations (
    wafer_operation_id INTEGER PRIMARY KEY,
    wafer_id TEXT NOT NULL REFERENCES wafers(wafer_id),
    operation_code TEXT NOT NULL REFERENCES operations(operation_code),
    tool_id TEXT NOT NULL REFERENCES tools(tool_id),
    sequence_number INTEGER NOT NULL,
    start_timestamp TEXT NOT NULL,
    end_timestamp TEXT,
    result TEXT NOT NULL,
    UNIQUE (wafer_id, operation_code)
);

CREATE TABLE IF NOT EXISTS defect_categories (
    defect_code TEXT PRIMARY KEY,
    defect_name TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inspections (
    inspection_id INTEGER PRIMARY KEY,
    wafer_id TEXT NOT NULL REFERENCES wafers(wafer_id),
    operation_code TEXT NOT NULL REFERENCES operations(operation_code),
    tool_id TEXT NOT NULL REFERENCES tools(tool_id),
    inspection_timestamp TEXT NOT NULL,
    sites_inspected INTEGER NOT NULL CHECK (sites_inspected > 0),
    defect_count INTEGER NOT NULL CHECK (defect_count >= 0)
);

CREATE TABLE IF NOT EXISTS inspection_defects (
    inspection_id INTEGER NOT NULL REFERENCES inspections(inspection_id),
    defect_code TEXT NOT NULL REFERENCES defect_categories(defect_code),
    defect_count INTEGER NOT NULL CHECK (defect_count > 0),
    PRIMARY KEY (inspection_id, defect_code)
);

CREATE TABLE IF NOT EXISTS yield_results (
    yield_result_id INTEGER PRIMARY KEY,
    wafer_id TEXT NOT NULL REFERENCES wafers(wafer_id),
    operation_code TEXT NOT NULL REFERENCES operations(operation_code),
    measured_timestamp TEXT NOT NULL,
    total_die INTEGER NOT NULL CHECK (total_die > 0),
    good_die INTEGER NOT NULL CHECK (good_die BETWEEN 0 AND total_die),
    yield_rate REAL NOT NULL CHECK (yield_rate BETWEEN 0.0 AND 1.0),
    UNIQUE (wafer_id, operation_code)
);

CREATE TABLE IF NOT EXISTS die_results (
    die_result_id INTEGER PRIMARY KEY,
    wafer_id TEXT NOT NULL REFERENCES wafers(wafer_id),
    yield_result_id INTEGER NOT NULL REFERENCES yield_results(yield_result_id),
    x_coordinate INTEGER NOT NULL,
    y_coordinate INTEGER NOT NULL,
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    test_bin TEXT NOT NULL,
    test_category TEXT NOT NULL,
    UNIQUE (wafer_id, x_coordinate, y_coordinate)
);

CREATE TABLE IF NOT EXISTS measurement_characteristics (
    characteristic_id TEXT PRIMARY KEY,
    operation_code TEXT NOT NULL REFERENCES operations(operation_code),
    characteristic_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    lower_spec_limit REAL,
    upper_spec_limit REAL,
    CHECK (lower_spec_limit IS NULL OR upper_spec_limit IS NULL OR lower_spec_limit < upper_spec_limit)
);

CREATE TABLE IF NOT EXISTS process_measurements (
    measurement_id INTEGER PRIMARY KEY,
    wafer_id TEXT NOT NULL REFERENCES wafers(wafer_id),
    operation_code TEXT NOT NULL REFERENCES operations(operation_code),
    tool_id TEXT NOT NULL REFERENCES tools(tool_id),
    characteristic_id TEXT NOT NULL REFERENCES measurement_characteristics(characteristic_id),
    measured_timestamp TEXT NOT NULL,
    source_arrival_timestamp TEXT NOT NULL,
    measured_value REAL NOT NULL,
    UNIQUE (wafer_id, characteristic_id)
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id INTEGER PRIMARY KEY,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    detected_timestamp TEXT NOT NULL,
    evidence TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_watermarks (
    source_name TEXT PRIMARY KEY,
    watermark_timestamp TEXT NOT NULL,
    observed_timestamp TEXT NOT NULL,
    expected_max_lag_minutes INTEGER NOT NULL CHECK (expected_max_lag_minutes > 0),
    row_count INTEGER NOT NULL CHECK (row_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_lots_work_order ON lots(work_order_id);
CREATE INDEX IF NOT EXISTS idx_wafers_lot ON wafers(lot_id);
CREATE INDEX IF NOT EXISTS idx_wafer_operations_tool ON wafer_operations(tool_id, operation_code);
CREATE INDEX IF NOT EXISTS idx_inspections_wafer ON inspections(wafer_id);
CREATE INDEX IF NOT EXISTS idx_yield_timestamp ON yield_results(measured_timestamp);
CREATE INDEX IF NOT EXISTS idx_die_results_wafer ON die_results(wafer_id, y_coordinate, x_coordinate);
CREATE INDEX IF NOT EXISTS idx_measurements_characteristic_time
    ON process_measurements(characteristic_id, measured_timestamp);
CREATE INDEX IF NOT EXISTS idx_measurements_tool_time
    ON process_measurements(tool_id, measured_timestamp);
CREATE INDEX IF NOT EXISTS idx_quality_issue_entity
    ON data_quality_issues(entity_type, entity_id);

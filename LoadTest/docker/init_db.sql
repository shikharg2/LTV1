-- Database Schema for Load Testing Framework
-- This schema stores test scenarios, runs, metrics, and evaluation results

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS load_test;

-- Set search path
SET search_path TO load_test, public;

-- Table 1: Scenarios
-- Stores test scenario configurations
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id UUID PRIMARY KEY,
    protocol VARCHAR(255),
    config_snapshot JSONB NOT NULL
);

-- Table 2: Test_Runs
-- Stores individual test run information
CREATE TABLE IF NOT EXISTS test_runs (
    run_id UUID PRIMARY KEY,
    scenario_id UUID NOT NULL REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL,
    worker_node VARCHAR(255)
);

-- Table 3: Raw_Metrics
-- Stores raw metric data collected during test runs
CREATE TABLE IF NOT EXISTS raw_metrics (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    metric_name VARCHAR(255) NOT NULL,
    metric_value VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL
);

-- Table 4: Results_Log
-- Stores evaluation results comparing expected vs measured values
CREATE TABLE IF NOT EXISTS results_log (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    metric_name VARCHAR(255) NOT NULL,
    expected_value VARCHAR(255),
    measured_value VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    scope VARCHAR(50) NOT NULL
);

-- Table 5: Scenario_Summary
-- Stores aggregated metrics after a scenario completes all runs
CREATE TABLE IF NOT EXISTS scenario_summary (
    id UUID PRIMARY KEY,
    scenario_id UUID NOT NULL REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    metric_name VARCHAR(255) NOT NULL,
    sample_count INTEGER NOT NULL,
    avg_value NUMERIC,
    min_value NUMERIC,
    max_value NUMERIC,
    p50_value NUMERIC,
    p99_value NUMERIC,
    stddev_value NUMERIC,
    aggregated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(scenario_id, metric_name)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_test_runs_scenario ON test_runs(scenario_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_start_time ON test_runs(start_time);
CREATE INDEX IF NOT EXISTS idx_raw_metrics_run ON raw_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_raw_metrics_name ON raw_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_raw_metrics_timestamp ON raw_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_results_log_run ON results_log(run_id);
CREATE INDEX IF NOT EXISTS idx_results_log_status ON results_log(status);
CREATE INDEX IF NOT EXISTS idx_results_log_scope ON results_log(scope);
CREATE INDEX IF NOT EXISTS idx_scenario_summary_scenario ON scenario_summary(scenario_id);

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON SCHEMA load_test TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA load_test TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA load_test TO postgres;

import os
import uuid
from datetime import datetime
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection_params() -> dict:
    """Get database connection parameters from environment variables."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "dbname": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
    }


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = psycopg2.connect(**get_connection_params())
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_scenario(scenario_id: str, protocol: str, config_snapshot: dict) -> None:
    """Insert a new scenario into the scenarios table."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO load_test.scenarios (scenario_id, protocol, config_snapshot)
                VALUES (%s, %s, %s)
                ON CONFLICT (scenario_id) DO UPDATE SET config_snapshot = EXCLUDED.config_snapshot
                """,
                (scenario_id, protocol, psycopg2.extras.Json(config_snapshot))
            )


def insert_test_run(run_id: str, scenario_id: str, start_time: datetime, worker_node: str) -> None:
    """Insert a new test run into the test_runs table."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO load_test.test_runs (run_id, scenario_id, start_time, worker_node)
                VALUES (%s, %s, %s, %s)
                """,
                (run_id, scenario_id, start_time, worker_node)
            )


def insert_raw_metric(run_id: str, metric_name: str, metric_value: str) -> None:
    """Insert a raw metric into the raw_metrics table."""
    metric_id = str(uuid.uuid4())
    timestamp = datetime.now()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO load_test.raw_metrics (id, run_id, metric_name, metric_value, timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (metric_id, run_id, metric_name, metric_value, timestamp)
            )


def insert_raw_metrics_batch(run_id: str, metrics: dict[str, float]) -> None:
    """Insert multiple raw metrics in a single transaction."""
    timestamp = datetime.now()
    with get_connection() as conn:
        with conn.cursor() as cur:
            for metric_name, metric_value in metrics.items():
                metric_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO load_test.raw_metrics (id, run_id, metric_name, metric_value, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (metric_id, run_id, metric_name, str(metric_value), timestamp)
                )


def insert_result_log(run_id: str, metric_name: str, expected_value: str,
                      measured_value: str, status: str, scope: str) -> None:
    """Insert a result log entry."""
    result_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO load_test.results_log (id, run_id, metric_name, expected_value, measured_value, status, scope)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (result_id, run_id, metric_name, expected_value, measured_value, status, scope)
            )


def get_raw_metrics_for_run(run_id: str) -> list[dict]:
    """Get all raw metrics for a specific run."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT metric_name, metric_value, timestamp
                FROM load_test.raw_metrics
                WHERE run_id = %s
                """,
                (run_id,)
            )
            return cur.fetchall()


def get_raw_metrics_for_scenario(scenario_id: str) -> list[dict]:
    """Get all raw metrics for a scenario (across all runs)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT rm.metric_name, rm.metric_value::NUMERIC as metric_value, rm.timestamp
                FROM load_test.raw_metrics rm
                JOIN load_test.test_runs tr ON rm.run_id = tr.run_id
                WHERE tr.scenario_id = %s
                """,
                (scenario_id,)
            )
            return cur.fetchall()


def insert_scenario_summary(scenario_id: str, metric_name: str, sample_count: int,
                            avg_value: float, min_value: float, max_value: float,
                            p50_value: float, p99_value: float, stddev_value: float) -> None:
    """Insert or update scenario summary."""
    summary_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO load_test.scenario_summary
                (id, scenario_id, metric_name, sample_count, avg_value, min_value, max_value, p50_value, p99_value, stddev_value, aggregated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (scenario_id, metric_name) DO UPDATE SET
                    sample_count = EXCLUDED.sample_count,
                    avg_value = EXCLUDED.avg_value,
                    min_value = EXCLUDED.min_value,
                    max_value = EXCLUDED.max_value,
                    p50_value = EXCLUDED.p50_value,
                    p99_value = EXCLUDED.p99_value,
                    stddev_value = EXCLUDED.stddev_value,
                    aggregated_at = NOW()
                """,
                (summary_id, scenario_id, metric_name, sample_count, avg_value,
                 min_value, max_value, p50_value, p99_value, stddev_value)
            )


def export_tables_to_csv(output_dir: str) -> None:
    """Export all tables to CSV files."""
    os.makedirs(output_dir, exist_ok=True)
    tables = ["scenarios", "test_runs", "raw_metrics", "results_log", "scenario_summary"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in tables:
                output_path = os.path.join(output_dir, f"{table}.csv")
                with open(output_path, "w") as f:
                    cur.copy_expert(
                        f"COPY load_test.{table} TO STDOUT WITH CSV HEADER",
                        f
                    )

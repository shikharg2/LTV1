import os
import uuid
import socket
from datetime import datetime, timedelta
from typing import Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from src.utils.db import insert_test_run, insert_raw_metrics_batch, insert_result_log
from src.utils.aggregator import aggregate_metrics_for_run, get_aggregated_value, save_scenario_summary
from src.utils.unit_converter import normalize_for_comparison
from src.test_modules.speed_test import run_speed_test
from src.test_modules.web_browsing import run_web_browsing_test


PROTOCOL_HANDLERS = {
    "speed_test": run_speed_test,
    "web_browsing": run_web_browsing_test,
}


class ScenarioScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scenario_jobs = {}  # scenario_id -> job_id mapping
        self.scenario_end_times = {}  # scenario_id -> end_time
        self.scenario_configs = {}  # scenario_id -> full config

    def start(self):
        """Start the scheduler."""
        self.scheduler.start()

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler."""
        self.scheduler.shutdown(wait=wait)

    def schedule_scenario(self, scenario_id: str, scenario_config: dict) -> None:
        """
        Schedule a scenario based on its configuration.
        """
        schedule = scenario_config.get("schedule", {})
        mode = schedule.get("mode", "once")
        start_time = schedule.get("start_time", "immediate")
        interval_minutes = schedule.get("interval_minutes", 10)
        duration_hours = schedule.get("duration_hours", 1)

        self.scenario_configs[scenario_id] = scenario_config

        # Calculate end time for recurring jobs
        if mode == "recurring":
            if start_time == "immediate":
                start_dt = datetime.now()
            else:
                start_dt = datetime.fromisoformat(start_time)
            end_time = start_dt + timedelta(hours=duration_hours)
            self.scenario_end_times[scenario_id] = end_time

        # Create the job function
        job_func = self._create_job_function(scenario_id, scenario_config)

        if mode == "once":
            if start_time == "immediate":
                # Run immediately
                trigger = DateTrigger(run_date=datetime.now())
            else:
                trigger = DateTrigger(run_date=datetime.fromisoformat(start_time))

            job = self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=f"scenario_{scenario_id}",
                name=f"Scenario {scenario_config.get('id', scenario_id)}",
            )
        else:  # recurring
            if start_time == "immediate":
                next_run = datetime.now()
            else:
                next_run = datetime.fromisoformat(start_time)

            trigger = IntervalTrigger(
                minutes=interval_minutes,
                start_date=next_run,
                end_date=self.scenario_end_times[scenario_id],
            )

            job = self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=f"scenario_{scenario_id}",
                name=f"Scenario {scenario_config.get('id', scenario_id)}",
            )

        self.scenario_jobs[scenario_id] = job.id

    def _create_job_function(self, scenario_id: str, scenario_config: dict) -> Callable:
        """Create a job function for the scenario."""

        def job_func():
            self._execute_test(scenario_id, scenario_config)

        return job_func

    def _execute_test(self, scenario_id: str, scenario_config: dict) -> None:
        """Execute a single test run for a scenario."""
        protocol = scenario_config.get("protocol")
        parameters = scenario_config.get("parameters", {})
        expectations = scenario_config.get("expectations", [])

        if protocol not in PROTOCOL_HANDLERS:
            print(f"Unknown protocol: {protocol}")
            return

        # Generate run_id and get worker node
        run_id = str(uuid.uuid4())
        worker_node = os.getenv("HOSTNAME", socket.gethostname())
        start_time = datetime.now()

        # Insert test run
        insert_test_run(run_id, scenario_id, start_time, worker_node)

        # Execute the test
        handler = PROTOCOL_HANDLERS[protocol]
        results = handler(parameters)

        # Write metrics to database
        for result in results:
            metrics = self._extract_metrics(result)
            insert_raw_metrics_batch(run_id, metrics)

        # Evaluate expectations for per_iteration scope
        self._evaluate_expectations(run_id, scenario_id, expectations, scope="per_iteration")

    def _extract_metrics(self, result) -> dict[str, float]:
        """Extract metrics from a test result object."""
        if hasattr(result, "__dataclass_fields__"):
            return {field: getattr(result, field) for field in result.__dataclass_fields__
                    if isinstance(getattr(result, field), (int, float))}
        elif isinstance(result, dict):
            return {k: v for k, v in result.items() if isinstance(v, (int, float))}
        return {}

    def _evaluate_expectations(self, run_id: str, scenario_id: str,
                               expectations: list, scope: str) -> None:
        """Evaluate expectations and write to results_log."""
        for expectation in expectations:
            if expectation.get("evaluation_scope") != scope:
                continue

            metric_name = expectation.get("metric")
            operator = expectation.get("operator")
            expected_value = expectation.get("value")
            expected_unit = expectation.get("unit", "")
            aggregation = expectation.get("aggregation", "avg")

            if scope == "per_iteration":
                metrics = aggregate_metrics_for_run(run_id)
                measured_value = metrics.get(metric_name, 0)
            else:  # scenario
                measured_value = get_aggregated_value(scenario_id, metric_name, aggregation)

            # Normalize units for comparison
            measured_normalized, expected_normalized = normalize_for_comparison(
                measured_value, expected_value, expected_unit, metric_name
            )

            status = self._compare_values(measured_normalized, operator, expected_normalized)

            insert_result_log(
                run_id=run_id,
                metric_name=metric_name,
                expected_value=f"{expected_value} {expected_unit}",
                measured_value=str(measured_value),
                status=status,
                scope=scope,
            )

    def _compare_values(self, measured: float, operator: str, expected: float) -> str:
        """Compare measured value against expected using operator."""
        comparisons = {
            "lte": measured <= expected,
            "lt": measured < expected,
            "gte": measured >= expected,
            "gt": measured > expected,
            "eq": measured == expected,
        }
        return "PASS" if comparisons.get(operator, False) else "FAIL"

    def finalize_scenario(self, scenario_id: str) -> None:
        """
        Finalize a scenario after all runs complete.
        Evaluates scenario-scope expectations and saves summary.
        """
        scenario_config = self.scenario_configs.get(scenario_id, {})
        expectations = scenario_config.get("expectations", [])

        # Get any run_id for this scenario to use for results_log
        from src.utils.db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT run_id FROM load_test.test_runs WHERE scenario_id = %s LIMIT 1",
                    (scenario_id,)
                )
                row = cur.fetchone()
                run_id = row[0] if row else str(uuid.uuid4())

        # Evaluate scenario-scope expectations
        self._evaluate_expectations(run_id, scenario_id, expectations, scope="scenario")

        # Save aggregated summary
        save_scenario_summary(scenario_id)

    def is_scenario_complete(self, scenario_id: str) -> bool:
        """Check if a scenario has completed all its scheduled runs."""
        if scenario_id not in self.scenario_end_times:
            # One-time job, check if it has run
            job_id = self.scenario_jobs.get(scenario_id)
            if job_id:
                job = self.scheduler.get_job(job_id)
                return job is None or job.next_run_time is None
            return True

        return datetime.now() >= self.scenario_end_times[scenario_id]

    def get_pending_jobs(self) -> list:
        """Get list of pending jobs."""
        return self.scheduler.get_jobs()

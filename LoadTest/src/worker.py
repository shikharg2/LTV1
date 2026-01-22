#!/usr/bin/env python3
"""
Worker module that runs inside Docker containers.
Executes scheduled tests for a specific scenario.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

from src.scheduler import ScenarioScheduler


def run_worker(scenario_id: str):
    """Run worker for a specific scenario."""
    # Get scenario config from environment
    scenario_config_str = os.getenv("SCENARIO_CONFIG")
    if not scenario_config_str:
        print(f"Error: SCENARIO_CONFIG not set for scenario {scenario_id}")
        sys.exit(1)

    scenario_config = json.loads(scenario_config_str)

    print(f"Worker starting for scenario: {scenario_config.get('id', scenario_id)}")
    print(f"  Protocol: {scenario_config.get('protocol')}")
    print(f"  Hostname: {os.getenv('HOSTNAME', 'unknown')}")

    # Create scheduler and schedule the scenario
    scheduler = ScenarioScheduler()
    scheduler.schedule_scenario(scenario_id, scenario_config)
    scheduler.start()

    # Calculate end time
    schedule = scenario_config.get("schedule", {})
    mode = schedule.get("mode", "once")
    duration_hours = schedule.get("duration_hours", 1)

    if mode == "once":
        # Wait for single execution to complete
        time.sleep(60)
    else:
        # Wait for full duration
        end_time = datetime.now() + timedelta(hours=duration_hours)
        while datetime.now() < end_time:
            if scheduler.is_scenario_complete(scenario_id):
                break
            time.sleep(30)

    # Finalize
    scheduler.finalize_scenario(scenario_id)
    scheduler.shutdown()

    print(f"Worker completed for scenario: {scenario_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.worker <scenario_id>")
        sys.exit(1)

    scenario_id = sys.argv[1]
    run_worker(scenario_id)

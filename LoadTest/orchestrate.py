#!/usr/bin/env python3
"""
Load Test Orchestrator

This module orchestrates load testing scenarios using Docker Swarm.
It reads configuration from main.json, manages PostgreSQL database,
schedules tests, and exports results.
"""

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.db import insert_scenario, export_tables_to_csv
from src.utils.uuid_generator import generate_uuid4
from src.scheduler import ScenarioScheduler


CONFIG_PATH = "configurations/main.json"
DOCKER_IMAGE = "loadtest:latest"
DB_CONTAINER_NAME = "db-container"
DB_VOLUME_NAME = "load-test"


def load_config(config_path: str = CONFIG_PATH) -> dict:
    """Load configuration from main.json."""
    with open(config_path, "r") as f:
        return json.load(f)


def setup_report_path(config: dict) -> str:
    """Create and return the report path from configuration."""
    report_path = config.get("global_settings", {}).get("report_path", "./results/")
    os.makedirs(report_path, exist_ok=True)
    return report_path


def start_postgres_container() -> None:
    """Start PostgreSQL container with Docker volume."""
    # Create volume if not exists
    subprocess.run(
        ["docker", "volume", "create", DB_VOLUME_NAME],
        capture_output=True
    )

    # Check if container already running
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={DB_CONTAINER_NAME}"],
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        print(f"Container {DB_CONTAINER_NAME} already running")
        return

    # Remove stopped container if exists
    subprocess.run(
        ["docker", "rm", "-f", DB_CONTAINER_NAME],
        capture_output=True
    )

    # Start PostgreSQL container
    subprocess.run([
        "docker", "run", "-d",
        "--name", DB_CONTAINER_NAME,
        "-e", "POSTGRES_PASSWORD=postgres",
        "-e", "POSTGRES_DB=postgres",
        "-v", f"{DB_VOLUME_NAME}:/var/lib/postgresql/data",
        "-p", "5432:5432",
        "--network", "loadtest-network",
        "-v", f"{os.path.abspath('docker/init_db.sql')}:/docker-entrypoint-initdb.d/init_db.sql",
        "postgres:16-alpine"
    ], check=True)

    # Wait for PostgreSQL to be ready
    print("Waiting for PostgreSQL to start...")
    time.sleep(10)


def ensure_docker_network() -> None:
    """Ensure Docker overlay network exists for Swarm service communication."""
    # Check if network already exists
    result = subprocess.run(
        ["docker", "network", "ls", "--filter", "name=loadtest-network", "--format", "{{.Name}}"],
        capture_output=True,
        text=True
    )

    if "loadtest-network" in result.stdout:
        print("  Network loadtest-network already exists")
        return

    # Create overlay network for Swarm services (attachable so regular containers can join)
    result = subprocess.run(
        ["docker", "network", "create", "--driver", "overlay", "--attachable", "loadtest-network"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"  Warning: Failed to create overlay network: {result.stderr}")
        # Fallback to bridge network for non-swarm mode
        print("  Attempting to create bridge network instead...")
        subprocess.run(
            ["docker", "network", "create", "loadtest-network"],
            capture_output=True
        )
    else:
        print("  Created overlay network: loadtest-network")


def init_docker_swarm() -> None:
    """Initialize Docker Swarm if not already active."""
    result = subprocess.run(
        ["docker", "info", "--format", "{{.Swarm.LocalNodeState}}"],
        capture_output=True,
        text=True
    )
    swarm_state = result.stdout.strip()
    print(f"  Swarm state: {swarm_state}")

    if swarm_state != "active":
        print("  Initializing Docker Swarm...")
        init_result = subprocess.run(
            ["docker", "swarm", "init"],
            capture_output=True,
            text=True
        )
        if init_result.returncode != 0:
            print(f"  Warning: Swarm init failed: {init_result.stderr}")
        else:
            print("  Swarm initialized successfully")
    else:
        print("  Swarm already active")


def deploy_test_service(scenario_id: str, scenario_config: dict, replicas: int = 1) -> str:
    """
    Deploy a Docker Swarm service for running tests in parallel.
    Returns the service name.
    """
    service_name = f"loadtest-{scenario_id[:8]}"
    protocol = scenario_config.get("protocol", "unknown")

    # Environment variables for the container
    env_vars = [
        "-e", f"SCENARIO_ID={scenario_id}",
        "-e", f"SCENARIO_CONFIG={json.dumps(scenario_config)}",
        "-e", "DB_HOST=db-container",
        "-e", "DB_PORT=5432",
        "-e", "DB_NAME=postgres",
        "-e", "DB_USER=postgres",
        "-e", "DB_PASSWORD=postgres",
    ]

    cmd = [
        "docker", "service", "create",
        "--name", service_name,
        "--replicas", str(replicas),
        "--network", "loadtest-network",
        "--restart-condition", "none",
    ] + env_vars + [
        DOCKER_IMAGE,
        "python3", "-m", "src.worker", scenario_id
    ]

    subprocess.run(cmd, check=True)
    return service_name


def remove_service(service_name: str) -> None:
    """Remove a Docker Swarm service."""
    subprocess.run(
        ["docker", "service", "rm", service_name],
        capture_output=True
    )


def calculate_total_duration(scenarios: list[dict]) -> timedelta:
    """Calculate the maximum duration across all scenarios."""
    max_duration = timedelta(0)
    for scenario in scenarios:
        if not scenario.get("enabled", False):
            continue
        schedule = scenario.get("schedule", {})
        duration_hours = schedule.get("duration_hours", 1)
        max_duration = max(max_duration, timedelta(hours=duration_hours))
    return max_duration


def orchestrate():
    """Main orchestration function."""
    print("=" * 60)
    print("Load Test Orchestrator Starting")
    print("=" * 60)

    # Step 1: Load configuration
    print("\n[1/7] Loading configuration...")
    config = load_config()

    # Step 2: Setup report path
    print("[2/7] Setting up report path...")
    report_path = setup_report_path(config)
    print(f"  Report path: {report_path}")

    # Step 3: Setup Docker infrastructure
    print("[3/7] Setting up Docker infrastructure...")
    init_docker_swarm()  # Must init swarm before creating overlay network
    ensure_docker_network()
    start_postgres_container()

    # Step 4: Process enabled scenarios
    print("[4/7] Processing scenarios...")
    scenarios = config.get("scenarios", [])
    scheduler = ScenarioScheduler()
    active_services = []
    scenario_ids = {}

    for scenario in scenarios:
        if not scenario.get("enabled", False):
            print(f"  Skipping disabled scenario: {scenario.get('id', 'unknown')}")
            continue

        # Generate UUID for scenario
        scenario_id = generate_uuid4()
        scenario_ids[scenario.get("id")] = scenario_id
        protocol = scenario.get("protocol", "unknown")

        print(f"  Processing scenario: {scenario.get('id')} ({protocol})")
        print(f"    UUID: {scenario_id}")

        # Step 5: Insert scenario into database
        insert_scenario(
            scenario_id=scenario_id,
            protocol=protocol,
            config_snapshot=scenario
        )

        # Step 6: Schedule the scenario
        scheduler.schedule_scenario(scenario_id, scenario)

        # Deploy Docker Swarm service for parallel execution
        service_name = deploy_test_service(scenario_id, scenario, replicas=1)
        active_services.append((service_name, scenario_id))

    # Step 7: Start scheduler and wait for completion
    print("[5/7] Starting scheduler...")
    scheduler.start()

    total_duration = calculate_total_duration(scenarios)
    print(f"  Total test duration: {total_duration}")

    # Monitor and wait for completion
    print("[6/7] Running tests...")
    start_time = datetime.now()
    end_time = start_time + total_duration + timedelta(minutes=5)  # Add buffer

    try:
        while datetime.now() < end_time:
            # Check if all scenarios are complete
            all_complete = all(
                scheduler.is_scenario_complete(sid)
                for sid in scenario_ids.values()
            )

            if all_complete:
                print("  All scenarios completed")
                break

            pending_jobs = scheduler.get_pending_jobs()
            print(f"  {len(pending_jobs)} jobs pending...", end="\r")
            time.sleep(30)

    except KeyboardInterrupt:
        print("\n  Interrupted by user")

    # Finalize scenarios (evaluate scenario-scope expectations)
    print("  Finalizing scenarios...")
    for scenario_id in scenario_ids.values():
        scheduler.finalize_scenario(scenario_id)

    scheduler.shutdown()

    # Cleanup services
    for service_name, _ in active_services:
        remove_service(service_name)

    # Step 8: Export results to CSV
    print("[7/7] Exporting results to CSV...")
    export_tables_to_csv(report_path)
    print(f"  Results exported to: {report_path}")

    print("\n" + "=" * 60)
    print("Orchestration Complete")
    print("=" * 60)


if __name__ == "__main__":
    orchestrate()

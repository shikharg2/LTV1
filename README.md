# LoadTest

A distributed load testing framework that orchestrates performance testing scenarios using Docker Swarm and PostgreSQL. It supports multiple testing protocols and provides comprehensive metrics collection, statistical aggregation, and automated pass/fail evaluation against configurable expectations.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [Global Settings](#global-settings)
  - [Scenario Configuration](#scenario-configuration)
  - [Schedule Options](#schedule-options)
  - [Protocol Parameters](#protocol-parameters)
  - [Expectations](#expectations)
- [Supported Protocols](#supported-protocols)
  - [Speed Test](#speed-test)
  - [Web Browsing](#web-browsing)
- [Output and Results](#output-and-results)
- [Environment Variables](#environment-variables)

## Features

- **Multiple Test Protocols**: Speed tests (iperf3) and web browsing tests (Playwright)
- **Distributed Execution**: Run tests across multiple Docker containers via Docker Swarm
- **Flexible Scheduling**: One-time or recurring test execution with configurable intervals
- **Statistical Aggregation**: Automatic calculation of avg, min, max, p50, p99, and stddev
- **Expectation Evaluation**: Define pass/fail thresholds for metrics at per-iteration or scenario scope
- **CSV Reporting**: Comprehensive export of raw metrics, aggregated summaries, and results

## Architecture

```
┌─────────────────┐
│  orchestrate.py │  ← Main entry point
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  Docker Swarm   │────▶│  Worker Nodes    │
│  Service        │     │  (src/worker.py) │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│   PostgreSQL    │◀────│  Test Modules    │
│   Database      │     │  - speed_test    │
└─────────────────┘     │  - web_browsing  │
                        └──────────────────┘
```

## Prerequisites

- Docker (with Docker Swarm support)
- Python 3.12+
- iperf3 server (for speed tests)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd LoadTest
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

5. **Build Docker image**:
   ```bash
   docker build -t loadtest:latest .
   ```

## Quick Start

1. Edit the configuration file at `configurations/main.json` (see [Configuration](#configuration))

2. Run the orchestrator:
   ```bash
   python3 orchestrate.py
   ```

3. View results in the `results/` directory (CSV files)

## Configuration

All test configuration is defined in `configurations/main.json`.

### Global Settings

| Parameter | Type | Description |
|-----------|------|-------------|
| `report_path` | string | Output directory for CSV result files |
| `log_level` | string | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

```json
{
  "global_settings": {
    "report_path": "./results/speed_test/",
    "log_level": "INFO"
  }
}
```

### Scenario Configuration

Each scenario in the `scenarios` array supports the following parameters:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Unique identifier for the scenario |
| `description` | string | No | Human-readable description |
| `enabled` | boolean | Yes | Enable/disable the scenario |
| `protocol` | string | Yes | Test type: `speed_test` or `web_browsing` |
| `schedule` | object | Yes | Scheduling configuration (see below) |
| `parameters` | object | Yes | Protocol-specific parameters |
| `expectations` | array | No | Pass/fail thresholds for metrics |

### Schedule Options

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mode` | string | Yes | `once` - single execution, `recurring` - repeated execution |
| `start_time` | string | Yes | `immediate` or ISO 8601 datetime (e.g., `2024-01-15T10:00:00`) |
| `interval_minutes` | number | For recurring | Interval between test executions |
| `duration_hours` | number | For recurring | Total duration to run recurring tests |

```json
{
  "schedule": {
    "mode": "recurring",
    "start_time": "immediate",
    "interval_minutes": 5,
    "duration_hours": 1
  }
}
```

### Protocol Parameters

#### Speed Test Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `target_url` | array[string] | Yes | List of iperf3 servers in `host:port` format |
| `duration` | number | No | Test duration in seconds (default: 5) |

```json
{
  "protocol": "speed_test",
  "parameters": {
    "target_url": ["speedtest.example.com:5201"],
    "duration": 10
  }
}
```

#### Web Browsing Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `target_url` | array[string] | Yes | List of URLs to test |
| `headless` | boolean | No | Run browser in headless mode (default: true) |

```json
{
  "protocol": "web_browsing",
  "parameters": {
    "target_url": ["https://www.google.com", "https://www.example.com"],
    "headless": true
  }
}
```

### Expectations

Define pass/fail criteria for metrics. Multiple expectations can be defined per scenario.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `metric` | string | Yes | Name of the metric to evaluate |
| `operator` | string | Yes | Comparison operator: `lt`, `lte`, `gt`, `gte`, `eq` |
| `value` | number | Yes | Threshold value |
| `unit` | string | Yes | Unit of measurement (auto-converted) |
| `aggregation` | string | Yes | Statistical function: `avg`, `min`, `max`, `p50`, `p99`, `stddev` |
| `evaluation_scope` | string | Yes | When to evaluate: `per_iteration` or `scenario` |

**Operators:**
- `lt` - less than (<)
- `lte` - less than or equal (<=)
- `gt` - greater than (>)
- `gte` - greater than or equal (>=)
- `eq` - equal (=)

**Evaluation Scopes:**
- `per_iteration` - Evaluate after each test run
- `scenario` - Evaluate after all runs complete using aggregated scenario statistics

```json
{
  "expectations": [
    {
      "metric": "download_speed",
      "operator": "gte",
      "value": 100,
      "unit": "mbps",
      "aggregation": "avg",
      "evaluation_scope": "scenario"
    },
    {
      "metric": "page_load_time",
      "operator": "lte",
      "value": 3000,
      "unit": "ms",
      "aggregation": "p99",
      "evaluation_scope": "per_iteration"
    }
  ]
}
```

## Supported Protocols

### Speed Test

Uses `iperf3` for network performance testing.

**Metrics Collected:**

| Metric | Unit | Description |
|--------|------|-------------|
| `download_speed` | Mbps | Server-to-client throughput |
| `upload_speed` | Mbps | Client-to-server throughput |
| `jitter` | ms | Network jitter |
| `latency` | ms | Round-trip time (RTT) |

### Web Browsing

Uses Playwright with Chromium for browser-based testing.

**Metrics Collected:**

| Metric | Unit | Description |
|--------|------|-------------|
| `page_load_time` | ms | Total page load duration |
| `ttfb` | ms | Time to first byte |
| `dom_content_loaded` | ms | DOM content loaded time |
| `http_response_code` | - | HTTP status code |
| `resource_count` | count | Number of resources loaded |
| `redirect_count` | count | Number of redirects |

## Output and Results

Results are exported as CSV files to the configured `report_path` directory:

| File | Description |
|------|-------------|
| `scenarios.csv` | Scenario configurations and metadata |
| `test_runs.csv` | Individual test run records |
| `raw_metrics.csv` | All individual metric measurements |
| `scenario_summary.csv` | Aggregated statistics per metric per scenario |
| `results_log.csv` | Pass/fail evaluation results |

### Raw Metrics Format

```csv
id,run_id,metric_name,metric_value,timestamp
uuid,uuid,download_speed,150.5,2024-01-15 10:00:00
```

### Scenario Summary Format

```csv
id,scenario_id,metric_name,sample_count,avg_value,min_value,max_value,p50_value,p99_value,stddev_value,aggregated_at
```

### Results Log Format

```csv
id,run_id,metric_name,expected_value,measured_value,status,scope
uuid,uuid,download_speed,100,150.5,PASS,scenario
```

## Environment Variables

These are used internally by Docker workers:

| Variable | Description |
|----------|-------------|
| `DB_HOST` | PostgreSQL hostname (default: `db-container`) |
| `DB_PORT` | PostgreSQL port (default: `5432`) |
| `DB_NAME` | Database name (default: `postgres`) |
| `DB_USER` | Database user (default: `postgres`) |
| `DB_PASSWORD` | Database password (default: `postgres`) |
| `SCENARIO_ID` | UUID of the scenario being executed |
| `SCENARIO_CONFIG` | JSON-encoded scenario configuration |
| `HOSTNAME` | Worker node identifier |

## Unit Conversion

The framework automatically converts units to standard formats:

**Speed Units** (converted to Mbps):
- `bps`, `kbps`, `mbps`, `gbps`
- `Bps`, `KBps`, `MBps`, `GBps`

**Time Units** (converted to ms):
- `ns`, `us`, `ms`, `s`, `sec`, `seconds`, `min`, `minutes`

## Example Configuration

```json
{
  "global_settings": {
    "report_path": "./results/performance/",
    "log_level": "INFO"
  },
  "scenarios": [
    {
      "id": "network_speed_test",
      "description": "Test network throughput to iperf3 server",
      "enabled": true,
      "protocol": "speed_test",
      "schedule": {
        "mode": "recurring",
        "start_time": "immediate",
        "interval_minutes": 5,
        "duration_hours": 1
      },
      "parameters": {
        "target_url": ["speedtest.example.com:5201"],
        "duration": 10
      },
      "expectations": [
        {
          "metric": "download_speed",
          "operator": "gte",
          "value": 100,
          "unit": "mbps",
          "aggregation": "avg",
          "evaluation_scope": "scenario"
        },
        {
          "metric": "jitter",
          "operator": "lte",
          "value": 10,
          "unit": "ms",
          "aggregation": "p99",
          "evaluation_scope": "scenario"
        }
      ]
    },
    {
      "id": "website_performance",
      "description": "Monitor website load times",
      "enabled": true,
      "protocol": "web_browsing",
      "schedule": {
        "mode": "recurring",
        "start_time": "immediate",
        "interval_minutes": 10,
        "duration_hours": 2
      },
      "parameters": {
        "target_url": [
          "https://www.google.com",
          "https://www.youtube.com"
        ],
        "headless": true
      },
      "expectations": [
        {
          "metric": "page_load_time",
          "operator": "lte",
          "value": 5000,
          "unit": "ms",
          "aggregation": "p99",
          "evaluation_scope": "per_iteration"
        },
        {
          "metric": "ttfb",
          "operator": "lte",
          "value": 500,
          "unit": "ms",
          "aggregation": "avg",
          "evaluation_scope": "scenario"
        }
      ]
    }
  ]
}
```

## Project Structure

```
LoadTest/
├── orchestrate.py           # Main orchestrator entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker container definition
├── configurations/
│   └── main.json            # Test scenario configuration
├── docker/
│   └── init_db.sql          # Database schema initialization
├── src/
│   ├── scheduler.py         # Scenario scheduling and execution
│   ├── worker.py            # Docker worker process
│   ├── test_modules/
│   │   ├── speed_test.py    # iperf3-based speed testing
│   │   └── web_browsing.py  # Playwright-based web tests
│   └── utils/
│       ├── db.py            # Database operations
│       ├── aggregator.py    # Metrics aggregation
│       ├── unit_converter.py # Unit conversion utilities
│       └── uuid_generator.py # UUID generation
└── results/                 # Output directory for CSV reports
```

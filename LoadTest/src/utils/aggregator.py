import statistics
from collections import defaultdict
from src.utils.db import get_raw_metrics_for_scenario, get_raw_metrics_for_run, insert_scenario_summary


def calculate_percentile(values: list[float], percentile: float) -> float:
    """Calculate the given percentile of a list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def aggregate_metrics_for_run(run_id: str) -> dict[str, float]:
    """
    Aggregate metrics for a single run (per_iteration scope).
    Returns average value per metric for the run.
    """
    raw_metrics = get_raw_metrics_for_run(run_id)
    metrics_by_name = defaultdict(list)

    for metric in raw_metrics:
        try:
            value = float(metric["metric_value"])
            metrics_by_name[metric["metric_name"]].append(value)
        except (ValueError, TypeError):
            continue

    aggregated = {}
    for metric_name, values in metrics_by_name.items():
        if values:
            aggregated[metric_name] = statistics.mean(values)

    return aggregated


def aggregate_metrics_for_scenario(scenario_id: str) -> dict[str, dict]:
    """
    Aggregate metrics for an entire scenario (across all runs).
    Returns full statistics per metric.
    """
    raw_metrics = get_raw_metrics_for_scenario(scenario_id)
    metrics_by_name = defaultdict(list)

    for metric in raw_metrics:
        try:
            value = float(metric["metric_value"])
            metrics_by_name[metric["metric_name"]].append(value)
        except (ValueError, TypeError):
            continue

    aggregated = {}
    for metric_name, values in metrics_by_name.items():
        if values:
            aggregated[metric_name] = {
                "sample_count": len(values),
                "avg": statistics.mean(values),
                "min": min(values),
                "max": max(values),
                "p50": calculate_percentile(values, 0.50),
                "p99": calculate_percentile(values, 0.99),
                "stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
            }

    return aggregated


def get_aggregated_value(scenario_id: str, metric_name: str, aggregation: str) -> float:
    """
    Get a specific aggregated value for a metric.
    aggregation can be: avg, min, max, p50, p99, stddev
    """
    all_aggregated = aggregate_metrics_for_scenario(scenario_id)
    if metric_name not in all_aggregated:
        return 0.0

    metric_stats = all_aggregated[metric_name]
    return metric_stats.get(aggregation, metric_stats.get("avg", 0.0))


def save_scenario_summary(scenario_id: str) -> None:
    """
    Calculate and save aggregated metrics to scenario_summary table.
    Called after scenario completes all runs.
    """
    aggregated = aggregate_metrics_for_scenario(scenario_id)

    for metric_name, stats in aggregated.items():
        insert_scenario_summary(
            scenario_id=scenario_id,
            metric_name=metric_name,
            sample_count=stats["sample_count"],
            avg_value=stats["avg"],
            min_value=stats["min"],
            max_value=stats["max"],
            p50_value=stats["p50"],
            p99_value=stats["p99"],
            stddev_value=stats["stddev"],
        )

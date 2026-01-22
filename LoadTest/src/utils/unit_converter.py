"""
Unit conversion utilities for metric comparisons.

Standard units used by test modules:
- Speed: Mbps (megabits per second)
- Time: ms (milliseconds)
- Count: integer (no unit)
"""

# Conversion factors to standard units
# Format: {unit: (multiplier_to_standard, standard_unit)}
SPEED_CONVERSIONS = {
    "bps": (1 / 1_000_000, "mbps"),
    "kbps": (1 / 1_000, "mbps"),
    "mbps": (1, "mbps"),
    "gbps": (1_000, "mbps"),
    "Bps": (8 / 1_000_000, "mbps"),  # Bytes per second
    "KBps": (8 / 1_000, "mbps"),
    "MBps": (8, "mbps"),
    "GBps": (8_000, "mbps"),
}

TIME_CONVERSIONS = {
    "ns": (1 / 1_000_000, "ms"),
    "us": (1 / 1_000, "ms"),
    "ms": (1, "ms"),
    "s": (1_000, "ms"),
    "sec": (1_000, "ms"),
    "seconds": (1_000, "ms"),
    "min": (60_000, "ms"),
    "minutes": (60_000, "ms"),
}

COUNT_CONVERSIONS = {
    "count": (1, "count"),
    "": (1, "count"),
}

# Metric to unit category mapping
METRIC_CATEGORIES = {
    # Speed metrics
    "download_speed": "speed",
    "upload_speed": "speed",
    # Time metrics
    "latency": "time",
    "jitter": "time",
    "page_load_time": "time",
    "ttfb": "time",
    "dom_content_loaded": "time",
    # Count metrics
    "resource_count": "count",
    "redirect_count": "count",
    "http_response_code": "count",
}


def get_conversion_table(category: str) -> dict:
    """Get the conversion table for a category."""
    tables = {
        "speed": SPEED_CONVERSIONS,
        "time": TIME_CONVERSIONS,
        "count": COUNT_CONVERSIONS,
    }
    return tables.get(category, COUNT_CONVERSIONS)


def convert_to_standard(value: float, unit: str, metric_name: str) -> float:
    """
    Convert a value from the given unit to the standard unit for that metric.

    Args:
        value: The value to convert
        unit: The source unit (e.g., "mbps", "s", "ms")
        metric_name: The metric name to determine the category

    Returns:
        Value in standard units
    """
    category = METRIC_CATEGORIES.get(metric_name, "count")
    conversion_table = get_conversion_table(category)

    unit_lower = unit.lower() if unit else ""

    if unit_lower in conversion_table:
        multiplier, _ = conversion_table[unit_lower]
        return value * multiplier

    # If unit not recognized, return as-is
    return value


def convert_from_standard(value: float, target_unit: str, metric_name: str) -> float:
    """
    Convert a value from standard unit to the target unit.

    Args:
        value: The value in standard units
        target_unit: The target unit to convert to
        metric_name: The metric name to determine the category

    Returns:
        Value in target units
    """
    category = METRIC_CATEGORIES.get(metric_name, "count")
    conversion_table = get_conversion_table(category)

    unit_lower = target_unit.lower() if target_unit else ""

    if unit_lower in conversion_table:
        multiplier, _ = conversion_table[unit_lower]
        if multiplier != 0:
            return value / multiplier

    return value


def get_standard_unit(metric_name: str) -> str:
    """Get the standard unit for a metric."""
    category = METRIC_CATEGORIES.get(metric_name, "count")
    standard_units = {
        "speed": "mbps",
        "time": "ms",
        "count": "count",
    }
    return standard_units.get(category, "count")


def normalize_for_comparison(measured_value: float, expected_value: float,
                             expected_unit: str, metric_name: str) -> tuple[float, float]:
    """
    Normalize measured and expected values to the same unit for comparison.

    Measured values are assumed to be in standard units (from test modules).
    Expected values are converted from their specified unit to standard units.

    Args:
        measured_value: Value from test module (in standard units)
        expected_value: Value from expectations (in specified unit)
        expected_unit: Unit of the expected value
        metric_name: The metric being compared

    Returns:
        Tuple of (measured, expected) both in standard units
    """
    # Measured is already in standard units
    # Convert expected to standard units
    expected_normalized = convert_to_standard(expected_value, expected_unit, metric_name)

    return measured_value, expected_normalized

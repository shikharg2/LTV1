import subprocess
import json
from dataclasses import dataclass


@dataclass
class SpeedTestResult:
    download_speed: float  # Mbps
    upload_speed: float    # Mbps
    jitter: float          # ms
    latency: float         # ms


def run_speed_test(parameters: dict) -> list[SpeedTestResult]:
    """
    Run iperf3 speed tests based on parameters.

    Args:
        parameters: dict with 'target_url' (list of ip:port or domain:port)
                    and 'duration' (seconds)

    Returns:
        List of SpeedTestResult for each target URL
    """
    target_urls = parameters.get("target_url", [])
    duration = parameters.get("duration", 10)

    results = []
    for url in target_urls:
        host, port = _parse_url(url)
        result = _run_iperf3_test(host, port, duration)
        results.append(result)

    return results


def _parse_url(url: str) -> tuple[str, int]:
    """Parse ip:port or domain:port format."""
    parts = url.rsplit(":", 1)
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 5201
    return host, port


def _run_iperf3_test(host: str, port: int, duration: int) -> SpeedTestResult:
    """Run iperf3 test and collect metrics."""
    # Download test (default mode - client receives from server)
    download_result = _execute_iperf3(host, port, duration, reverse=True)
    download_speed = _extract_speed(download_result)
    download_jitter = _extract_jitter(download_result)
    download_latency = _extract_latency(download_result)

    # Upload test (client sends to server)
    upload_result = _execute_iperf3(host, port, duration, reverse=False)
    upload_speed = _extract_speed(upload_result)
    upload_jitter = _extract_jitter(upload_result)

    return SpeedTestResult(
        download_speed=download_speed,
        upload_speed=upload_speed,
        jitter=max(download_jitter, upload_jitter),
        latency=download_latency
    )


def _execute_iperf3(host: str, port: int, duration: int, reverse: bool) -> dict:
    """Execute iperf3 command and return JSON output."""
    cmd = [
        "iperf3",
        "-c", host,
        "-p", str(port),
        "-t", str(duration),
        "-J",  # JSON output
        "-u",  # UDP for jitter measurement
    ]
    if reverse:
        cmd.append("-R")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)
        return json.loads(result.stdout) if result.stdout else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return {}


def _extract_speed(data: dict) -> float:
    """Extract speed in Mbps from iperf3 JSON output."""
    try:
        end = data.get("end", {})
        sum_data = end.get("sum", {}) or end.get("sum_received", {})
        bits_per_second = sum_data.get("bits_per_second", 0)
        return bits_per_second / 1_000_000
    except (KeyError, TypeError):
        return 0.0


def _extract_jitter(data: dict) -> float:
    """Extract jitter in ms from iperf3 JSON output."""
    try:
        end = data.get("end", {})
        sum_data = end.get("sum", {})
        return sum_data.get("jitter_ms", 0.0)
    except (KeyError, TypeError):
        return 0.0


def _extract_latency(data: dict) -> float:
    """Extract latency (RTT) in ms from iperf3 JSON output."""
    try:
        streams = data.get("end", {}).get("streams", [])
        if streams:
            sender = streams[0].get("sender", {})
            return sender.get("mean_rtt", 0) / 1000  # Convert from microseconds
        return 0.0
    except (KeyError, TypeError, IndexError):
        return 0.0

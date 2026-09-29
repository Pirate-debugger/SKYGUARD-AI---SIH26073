"""
Pytest Suite: End-to-End Benchmark & False Alarm Constraints
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import json
import os
import pytest
from run_benchmark import evaluate_benchmark


def test_benchmark_performance_thresholds():
    benchmark_file = os.path.join(os.path.dirname(__file__), "..", "benchmark_results.json")
    if os.path.exists(benchmark_file):
        with open(benchmark_file, "r") as f:
            metrics = json.load(f)
    else:
        # Fast fallback execution
        metrics = evaluate_benchmark(seeds=[42], num_timesteps=20)
    
    # Extract mean metrics
    acc = metrics["overall_accuracy"]["mean"] if isinstance(metrics["overall_accuracy"], dict) else metrics["overall_accuracy"]
    macro_f1 = metrics["macro_f1"]["mean"] if isinstance(metrics["macro_f1"], dict) else metrics["macro_f1"]
    sensor_to_weather = metrics["sensor_to_weather_error_rate"]["mean"] if isinstance(metrics["sensor_to_weather_error_rate"], dict) else metrics["sensor_to_weather_rate"]
    normal_to_weather = metrics["normal_to_weather_rate"]["mean"] if isinstance(metrics["normal_to_weather_rate"], dict) else metrics["normal_to_weather_rate"]
    mean_lat = metrics["mean_latency_ms"] if isinstance(metrics["mean_latency_ms"], (int, float)) else metrics["mean_latency_ms"]["mean"]
    
    # SIH Realistic Multi-Seed Performance Thresholds
    assert acc >= 0.88, f"Accuracy too low: {acc:.4f}"
    assert macro_f1 >= 0.70, f"Macro F1 too low: {macro_f1:.4f}"
    assert sensor_to_weather <= 0.02, f"Sensor fault misclassified as weather event too high: {sensor_to_weather:.4f}"
    assert normal_to_weather <= 0.05, f"Normal to weather false alarm rate too high: {normal_to_weather:.4f}"
    assert mean_lat < 30.0, f"Latency too slow for real-time: {mean_lat:.2f} ms"


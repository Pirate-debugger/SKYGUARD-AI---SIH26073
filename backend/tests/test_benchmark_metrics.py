"""
Pytest Suite: End-to-End Benchmark & False Alarm Constraints
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import pytest
from run_benchmark import evaluate_benchmark


def test_benchmark_performance_thresholds():
    metrics = evaluate_benchmark()
    
    # SIH Strict Performance Thresholds
    assert metrics["overall_accuracy"] >= 0.95, f"Accuracy too low: {metrics['overall_accuracy']:.4f}"
    assert metrics["macro_precision"] >= 0.85, f"Macro precision too low: {metrics['macro_precision']:.4f}"
    assert metrics["macro_recall"] >= 0.90, f"Macro recall too low: {metrics['macro_recall']:.4f}"
    assert metrics["macro_f1"] >= 0.85, f"Macro F1 too low: {metrics['macro_f1']:.4f}"
    assert metrics["normal_to_weather_rate"] <= 0.05, f"Normal to weather false alarm rate too high: {metrics['normal_to_weather_rate']:.4f}"
    assert metrics["weather_to_sensor_rate"] <= 0.05, f"Weather event to sensor fault error rate too high: {metrics['weather_to_sensor_rate']:.4f}"
    assert metrics["mean_latency_ms"] < 30.0, f"Latency too slow for real-time: {metrics['mean_latency_ms']:.2f} ms"

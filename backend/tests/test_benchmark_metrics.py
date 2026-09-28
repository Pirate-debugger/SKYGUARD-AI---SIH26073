"""
Pytest Suite: End-to-End Benchmark & False Alarm Constraints
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import pytest
from run_benchmark import evaluate_benchmark


def test_benchmark_performance_thresholds():
    metrics = evaluate_benchmark()
    
    # SIH Strict Performance Thresholds
    assert metrics["accuracy"] >= 0.95, f"Accuracy too low: {metrics['accuracy']:.4f}"
    assert metrics["precision"] >= 0.90, f"Precision too low: {metrics['precision']:.4f}"
    assert metrics["recall"] >= 0.90, f"Recall too low: {metrics['recall']:.4f}"
    assert metrics["f1"] >= 0.90, f"F1 too low: {metrics['f1']:.4f}"
    assert metrics["false_alarm_rate"] <= 0.05, f"False alarm rate too high: {metrics['false_alarm_rate']:.4f}"
    assert metrics["weather_discrimination_acc"] >= 0.90, f"Weather event discrimination too low: {metrics['weather_discrimination_acc']:.4f}"
    assert metrics["avg_latency_ms"] < 20.0, f"Latency too slow for real-time: {metrics['avg_latency_ms']:.2f} ms"

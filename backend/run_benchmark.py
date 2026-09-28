"""
Multiclass Ground-Truth Benchmark & False Alarm Evaluation Suite for SkyGuard AI
SIH26073: AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations

Evaluates the complete synchronized pipeline against a controlled multiclass test matrix:
- Overall Multiclass Accuracy & Macro F1
- Per-Class Precision, Recall, F1, and Support
- Cross-Class Error Rates:
    * Normal -> Weather Event false-alert rate
    * Weather Event -> Sensor Fault false-alarm rate
    * Sensor Fault -> Weather Event misclassification rate
    * False Fault Rate per 1,000 observations
- Multiclass Confusion Matrix
- Mean & 95th Percentile Pipeline Latency (ms)
"""

import time
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import numpy as np

from app.models.schemas import DecisionClassification, ProbableCause
from app.simulator.generator import WeatherDataGenerator, DEFAULT_STATIONS
from app.core.pipeline import SkyGuardPipeline


# Canonical classes for multiclass evaluation
BENCHMARK_CLASSES = [
    "NORMAL",
    "REGIONAL_WEATHER_EVENT",
    "SENSOR_SPIKE",
    "SENSOR_FREEZE",
    "CALIBRATION_DRIFT",
    "COMMUNICATION_FAILURE",
    "DATA_CORRUPTION",
    "MULTIVARIATE_INCONSISTENCY",
    "SPATIAL_INCONSISTENCY"
]


def map_prediction_to_benchmark_class(decision: str, cause: str) -> str:
    """Maps system output (decision + root_cause) to the ground-truth benchmark categories."""
    if decision == "WEATHER_EVENT" or cause == "REGIONAL_WEATHER_EVENT":
        return "REGIONAL_WEATHER_EVENT"
    if decision == "COMMUNICATION_ERROR":
        if cause == "DATA_CORRUPTION":
            return "DATA_CORRUPTION"
        return "COMMUNICATION_FAILURE"
    if decision == "SENSOR_DEGRADATION" or cause == "CALIBRATION_DRIFT":
        return "CALIBRATION_DRIFT"
    if cause == "SENSOR_FREEZE":
        return "SENSOR_FREEZE"
    if cause == "SENSOR_SPIKE":
        return "SENSOR_SPIKE"
    if cause == "MULTIVARIATE_INCONSISTENCY":
        return "MULTIVARIATE_INCONSISTENCY"
    if cause == "SPATIAL_INCONSISTENCY":
        return "SPATIAL_INCONSISTENCY"
    if decision == "NORMAL":
        return "NORMAL"
    return "NORMAL"


def evaluate_benchmark():
    print("==================================================")
    print("SKYGUARD AI - SIH26073 MULTICLASS BENCHMARK")
    print("Evaluating Synchronized Pipeline Ground-Truth Matrix...")
    print("==================================================")

    pipeline = SkyGuardPipeline()
    generator = WeatherDataGenerator(stations=DEFAULT_STATIONS, seed=99)
    
    for st in DEFAULT_STATIONS:
        pipeline.spatial_engine.register_station(st)

    # 150 timesteps * 12 stations = 1800 observations
    num_timesteps = 150
    test_data = generator.generate_benchmark_dataset(num_timesteps=num_timesteps)
    print(f"Total Test Observations: {len(test_data)} across {num_timesteps} reporting windows.")

    # Group by timestamp for synchronized same-timestamp snapshot processing
    by_timestamp = defaultdict(list)
    for reading, gt_label in test_data:
        by_timestamp[reading.timestamp].append((reading, gt_label))

    y_true = []
    y_pred = []
    inference_latencies_ms = []

    for ts in sorted(by_timestamp.keys()):
        batch = by_timestamp[ts]
        raw_readings = [item[0] for item in batch]
        gt_labels = [item[1] for item in batch]

        t0 = time.perf_counter()
        batch_results = pipeline.process_batch(raw_readings)
        latency = ((time.perf_counter() - t0) * 1000.0) / len(raw_readings)

        for (processed, _), gt_label in zip(batch_results, gt_labels):
            inference_latencies_ms.append(latency)
            pred_class = map_prediction_to_benchmark_class(
                processed.decision.value,
                processed.probable_cause.value
            )
            y_true.append(gt_label)
            y_pred.append(pred_class)

    # --- Compute Multiclass Metrics ---
    classes = [c for c in BENCHMARK_CLASSES if c in set(y_true)]
    class_to_idx = {c: i for i, c in enumerate(classes)}
    
    cm = np.zeros((len(classes), len(classes)), dtype=int)
    for yt, yp in zip(y_true, y_pred):
        i = class_to_idx.get(yt, 0)
        j = class_to_idx.get(yp, 0)
        cm[i, j] += 1

    per_class_metrics = {}
    precisions = []
    recalls = []
    f1s = []

    for c in classes:
        idx = class_to_idx[c]
        tp = cm[idx, idx]
        fp = np.sum(cm[:, idx]) - tp
        fn = np.sum(cm[idx, :]) - tp
        support = int(np.sum(cm[idx, :]))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)

        per_class_metrics[c] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "support": support
        }

    overall_accuracy = float(np.sum(np.diag(cm))) / len(y_true)
    macro_precision = float(np.mean(precisions))
    macro_recall = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))

    # --- Cross-Class Operational Error Rates ---
    normal_idx = class_to_idx.get("NORMAL", 0)
    weather_idx = class_to_idx.get("REGIONAL_WEATHER_EVENT", 0)

    # 1. Normal -> Weather Event false alert rate
    normal_total = int(np.sum(cm[normal_idx, :]))
    normal_as_weather = int(cm[normal_idx, weather_idx])
    normal_to_weather_rate = normal_as_weather / normal_total if normal_total > 0 else 0.0

    # 2. Weather Event -> Sensor Fault false alarm rate
    weather_total = int(np.sum(cm[weather_idx, :]))
    weather_as_sensor = int(np.sum(cm[weather_idx, :]) - cm[weather_idx, weather_idx] - cm[weather_idx, normal_idx])
    weather_to_sensor_rate = weather_as_sensor / weather_total if weather_total > 0 else 0.0

    # 3. Sensor Fault -> Weather Event misclassification rate
    sensor_fault_total = 0
    sensor_fault_as_weather = 0
    for c in classes:
        if c not in ("NORMAL", "REGIONAL_WEATHER_EVENT"):
            s_idx = class_to_idx[c]
            sensor_fault_total += int(np.sum(cm[s_idx, :]))
            sensor_fault_as_weather += int(cm[s_idx, weather_idx])

    sensor_to_weather_rate = sensor_fault_as_weather / sensor_fault_total if sensor_fault_total > 0 else 0.0

    # 4. False Fault Rate per 1000 observations (clean points flagged as sensor fault)
    clean_points = normal_total + weather_total
    clean_flagged_as_fault = int(np.sum(cm[normal_idx, :]) - cm[normal_idx, normal_idx] - cm[normal_idx, weather_idx]) + weather_as_sensor
    false_fault_rate_per_1000 = (clean_flagged_as_fault / clean_points) * 1000.0 if clean_points > 0 else 0.0

    mean_latency = float(np.mean(inference_latencies_ms))
    p95_latency = float(np.percentile(inference_latencies_ms, 95))

    # --- Print Structured Benchmark Report ---
    print("\n--- MULTICLASS PERFORMANCE SUMMARY ---")
    print(f"Overall Classification Accuracy:          {overall_accuracy * 100:.2f}%")
    print(f"Macro Precision:                          {macro_precision * 100:.2f}%")
    print(f"Macro Recall:                             {macro_recall * 100:.2f}%")
    print(f"Macro F1 Score:                           {macro_f1 * 100:.2f}%")
    print("--------------------------------------------------")
    print("PER-CLASS METRICS:")
    print(f"{'Class':<28} | {'Precision':<10} | {'Recall':<10} | {'F1':<10} | {'Support':<8}")
    print("-" * 75)
    for c, m in per_class_metrics.items():
        print(f"{c:<28} | {m['precision']*100:>8.2f}% | {m['recall']*100:>8.2f}% | {m['f1']*100:>8.2f}% | {m['support']:>8}")

    print("\n--- OPERATIONAL CROSS-CLASS ERROR RATES ---")
    print(f"Normal -> Weather Event False Alert Rate: {normal_to_weather_rate * 100:.2f}% ({normal_as_weather}/{normal_total})")
    print(f"Weather Event -> Sensor Fault Alarm Rate: {weather_to_sensor_rate * 100:.2f}% ({weather_as_sensor}/{weather_total}) [Target: 0%]")
    print(f"Sensor Fault -> Weather Event Error Rate: {sensor_to_weather_rate * 100:.2f}% ({sensor_fault_as_weather}/{sensor_fault_total})")
    print(f"False Fault Rate per 1,000 Readings:      {false_fault_rate_per_1000:.2f} per 1000")
    print("--------------------------------------------------")
    print(f"Mean Pipeline Latency per Reading:        {mean_latency:.2f} ms")
    print(f"95th Percentile Latency:                  {p95_latency:.2f} ms")
    print("==================================================\n")

    # Print ASCII Confusion Matrix
    print("MULTICLASS CONFUSION MATRIX:")
    header = "Pred -> | " + " | ".join([f"{c[:8]:>8}" for c in classes])
    print(header)
    print("-" * len(header))
    for i, c in enumerate(classes):
        row_str = f"{c[:7]:<7} | " + " | ".join([f"{cm[i, j]:>8}" for j in range(len(classes))])
        print(row_str)
    print("==================================================\n")

    return {
        "overall_accuracy": overall_accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "normal_to_weather_rate": normal_to_weather_rate,
        "weather_to_sensor_rate": weather_to_sensor_rate,
        "sensor_to_weather_rate": sensor_to_weather_rate,
        "false_fault_rate_per_1000": false_fault_rate_per_1000,
        "mean_latency_ms": mean_latency,
        "p95_latency_ms": p95_latency,
        "per_class": per_class_metrics
    }


if __name__ == "__main__":
    evaluate_benchmark()

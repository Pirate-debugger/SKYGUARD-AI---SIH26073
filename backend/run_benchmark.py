"""
Multiclass Ground-Truth Benchmark & False Alarm Evaluation Suite for SkyGuard AI
SIH26073: AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations

Evaluates the complete synchronized pipeline against a balanced, multi-seed multiclass matrix:
- Balanced ground-truth dataset (>= 100 observations per canonical anomaly class)
- Multi-seed evaluation (seeds 42, 43, 44, 45, 46) reporting Mean ± Std, Min, Max
- Strictly NO silent mapping of UNKNOWN to NORMAL
- Overall Multiclass Accuracy & Macro F1
- Per-Class Precision, Recall, F1, and Support
- Cross-Class Error Rates:
    * Normal -> Weather Event false-alert rate
    * Normal -> Sensor Fault false-alarm rate
    * Weather Event -> Sensor Fault false-alarm rate
    * Weather Event -> Normal rate
    * Sensor Fault -> Weather Event misclassification rate
    * False Fault Rate per 1,000 observations
- Multiclass Confusion Matrix
- Mean & 95th Percentile Pipeline Latency (ms)
- Machine-readable JSON output (benchmark_results.json)
- Human-readable summary documentation (BENCHMARK.md)
"""

import os
import json
import time
from datetime import datetime, timezone
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
    "SPATIAL_INCONSISTENCY",
    "INSUFFICIENT_EVIDENCE",
    "UNKNOWN"
]


def map_prediction_to_benchmark_class(decision: str, cause: str) -> str:
    """
    Maps system output (decision + root_cause) to the ground-truth benchmark categories.
    STRICT P0 RULE: Unknown/unmapped predictions must NEVER default to NORMAL.
    """
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
    if cause == "DATA_CORRUPTION":
        return "DATA_CORRUPTION"
    if cause == "COMMUNICATION_FAILURE":
        return "COMMUNICATION_FAILURE"
    if cause == "MULTIVARIATE_INCONSISTENCY":
        return "MULTIVARIATE_INCONSISTENCY"
    if cause == "SPATIAL_INCONSISTENCY":
        return "SPATIAL_INCONSISTENCY"
    if decision == "INSUFFICIENT_EVIDENCE":
        return "INSUFFICIENT_EVIDENCE"
    if decision == "NORMAL":
        return "NORMAL"
    return "UNKNOWN"


def run_single_seed_benchmark(seed: int, num_timesteps: int = 360) -> Dict[str, Any]:
    pipeline = SkyGuardPipeline()
    generator = WeatherDataGenerator(stations=DEFAULT_STATIONS, seed=seed)
    
    for st in DEFAULT_STATIONS:
        pipeline.spatial_engine.register_station(st)

    test_data = generator.generate_benchmark_dataset(num_timesteps=num_timesteps)

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
                processed.decision.value if hasattr(processed.decision, "value") else str(processed.decision),
                processed.probable_cause.value if hasattr(processed.probable_cause, "value") else str(processed.probable_cause)
            )
            y_true.append(gt_label)
            y_pred.append(pred_class)

    # --- Compute Multiclass Metrics ---
    present_classes = sorted(list(set(y_true).union(set(y_pred))), key=lambda x: BENCHMARK_CLASSES.index(x) if x in BENCHMARK_CLASSES else 99)
    class_to_idx = {c: i for i, c in enumerate(present_classes)}
    
    cm = np.zeros((len(present_classes), len(present_classes)), dtype=int)
    for yt, yp in zip(y_true, y_pred):
        i = class_to_idx.get(yt, 0)
        j = class_to_idx.get(yp, 0)
        cm[i, j] += 1

    per_class_metrics = {}
    precisions = []
    recalls = []
    f1s = []

    for c in present_classes:
        idx = class_to_idx[c]
        tp = cm[idx, idx]
        fp = np.sum(cm[:, idx]) - tp
        fn = np.sum(cm[idx, :]) - tp
        support = int(np.sum(cm[idx, :]))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        if support > 0:
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
    macro_precision = float(np.mean(precisions)) if precisions else 0.0
    macro_recall = float(np.mean(recalls)) if recalls else 0.0
    macro_f1 = float(np.mean(f1s)) if f1s else 0.0

    # --- Cross-Class Operational Error Rates ---
    normal_idx = class_to_idx.get("NORMAL", 0)
    weather_idx = class_to_idx.get("REGIONAL_WEATHER_EVENT", 0)

    # 1. Normal -> Weather Event false alert rate
    normal_total = int(np.sum(cm[normal_idx, :]))
    normal_as_weather = int(cm[normal_idx, weather_idx]) if "REGIONAL_WEATHER_EVENT" in class_to_idx else 0
    normal_to_weather_rate = normal_as_weather / normal_total if normal_total > 0 else 0.0

    # 2. Weather Event -> Sensor Fault false alarm rate
    weather_total = int(np.sum(cm[weather_idx, :])) if "REGIONAL_WEATHER_EVENT" in class_to_idx else 0
    if weather_total > 0:
        weather_as_sensor = int(np.sum(cm[weather_idx, :]) - cm[weather_idx, weather_idx] - cm[weather_idx, normal_idx])
        weather_to_sensor_rate = weather_as_sensor / weather_total
    else:
        weather_as_sensor = 0
        weather_to_sensor_rate = 0.0

    # 3. Sensor Fault -> Weather Event misclassification rate
    sensor_fault_total = 0
    sensor_fault_as_weather = 0
    for c in present_classes:
        if c not in ("NORMAL", "REGIONAL_WEATHER_EVENT", "INSUFFICIENT_EVIDENCE", "UNKNOWN"):
            s_idx = class_to_idx[c]
            sensor_fault_total += int(np.sum(cm[s_idx, :]))
            if "REGIONAL_WEATHER_EVENT" in class_to_idx:
                sensor_fault_as_weather += int(cm[s_idx, weather_idx])

    sensor_to_weather_rate = sensor_fault_as_weather / sensor_fault_total if sensor_fault_total > 0 else 0.0

    # 4. Clean readings falsely flagged as sensor fault
    clean_points = normal_total + weather_total
    normal_as_fault = int(np.sum(cm[normal_idx, :]) - cm[normal_idx, normal_idx] - normal_as_weather)
    clean_flagged_as_fault = normal_as_fault + weather_as_sensor
    false_fault_rate_per_1000 = (clean_flagged_as_fault / clean_points) * 1000.0 if clean_points > 0 else 0.0

    mean_latency = float(np.mean(inference_latencies_ms))
    p95_latency = float(np.percentile(inference_latencies_ms, 95))

    return {
        "seed": seed,
        "total_observations": len(y_true),
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
        "per_class": per_class_metrics,
        "confusion_matrix": cm.tolist(),
        "classes": present_classes
    }


def evaluate_benchmark(seeds: List[int] = [42, 43, 44, 45, 46], num_timesteps: int = 360) -> Dict[str, Any]:
    print("==================================================")
    print("SKYGUARD AI — SIH26073 MULTICLASS BENCHMARK")
    print(f"Evaluating Synchronized Pipeline across {len(seeds)} Seeds (N={num_timesteps*12} per seed)...")
    print("==================================================")

    seed_results = []
    for s in seeds:
        print(f"-> Running evaluation for seed={s}...")
        res = run_single_seed_benchmark(seed=s, num_timesteps=num_timesteps)
        seed_results.append(res)
        print(f"   Seed {s}: Acc={res['overall_accuracy']*100:.2f}%, Macro-F1={res['macro_f1']*100:.2f}%, W->Sensor FAR={res['weather_to_sensor_rate']*100:.2f}%")

    # Aggregate metrics across seeds
    accs = [r["overall_accuracy"] for r in seed_results]
    macro_f1s = [r["macro_f1"] for r in seed_results]
    macro_precs = [r["macro_precision"] for r in seed_results]
    macro_recs = [r["macro_recall"] for r in seed_results]
    w_to_s_rates = [r["weather_to_sensor_rate"] for r in seed_results]
    s_to_w_rates = [r["sensor_to_weather_rate"] for r in seed_results]
    n_to_w_rates = [r["normal_to_weather_rate"] for r in seed_results]
    ff_rates = [r["false_fault_rate_per_1000"] for r in seed_results]
    latencies = [r["mean_latency_ms"] for r in seed_results]
    p95_lats = [r["p95_latency_ms"] for r in seed_results]

    summary = {
        "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_seeds": len(seeds),
        "seeds_evaluated": seeds,
        "observations_per_seed": seed_results[0]["total_observations"],
        "overall_accuracy": {
            "mean": float(np.mean(accs)),
            "std": float(np.std(accs)),
            "min": float(np.min(accs)),
            "max": float(np.max(accs))
        },
        "macro_f1": {
            "mean": float(np.mean(macro_f1s)),
            "std": float(np.std(macro_f1s)),
            "min": float(np.min(macro_f1s)),
            "max": float(np.max(macro_f1s))
        },
        "macro_precision": {
            "mean": float(np.mean(macro_precs)),
            "std": float(np.std(macro_precs)),
            "min": float(np.min(macro_precs)),
            "max": float(np.max(macro_precs))
        },
        "macro_recall": {
            "mean": float(np.mean(macro_recs)),
            "std": float(np.std(macro_recs)),
            "min": float(np.min(macro_recs)),
            "max": float(np.max(macro_recs))
        },
        "weather_to_sensor_false_alarm_rate": {
            "mean": float(np.mean(w_to_s_rates)),
            "std": float(np.std(w_to_s_rates)),
            "min": float(np.min(w_to_s_rates)),
            "max": float(np.max(w_to_s_rates))
        },
        "sensor_to_weather_error_rate": {
            "mean": float(np.mean(s_to_w_rates)),
            "std": float(np.std(s_to_w_rates)),
            "min": float(np.min(s_to_w_rates)),
            "max": float(np.max(s_to_w_rates))
        },
        "normal_to_weather_rate": {
            "mean": float(np.mean(n_to_w_rates)),
            "std": float(np.std(n_to_w_rates))
        },
        "false_fault_rate_per_1000": {
            "mean": float(np.mean(ff_rates)),
            "std": float(np.std(ff_rates))
        },
        "mean_latency_ms": float(np.mean(latencies)),
        "p95_latency_ms": float(np.mean(p95_lats)),
        "seed_runs": seed_results
    }

    # Reference seed run for per-class report (seed 42)
    ref_run = seed_results[0]
    classes = ref_run["classes"]
    cm = np.array(ref_run["confusion_matrix"])

    print("\n==================================================")
    print("SKYGUARD AI — MULTI-SEED BENCHMARK SUMMARY (N=5 SEEDS)")
    print("==================================================")
    print(f"Overall Accuracy:                  {summary['overall_accuracy']['mean']*100:.2f}% ± {summary['overall_accuracy']['std']*100:.2f}% [Min: {summary['overall_accuracy']['min']*100:.2f}%, Max: {summary['overall_accuracy']['max']*100:.2f}%]")
    print(f"Macro Precision:                   {summary['macro_precision']['mean']*100:.2f}% ± {summary['macro_precision']['std']*100:.2f}%")
    print(f"Macro Recall:                      {summary['macro_recall']['mean']*100:.2f}% ± {summary['macro_recall']['std']*100:.2f}%")
    print(f"Macro F1-Score:                    {summary['macro_f1']['mean']*100:.2f}% ± {summary['macro_f1']['std']*100:.2f}% [Min: {summary['macro_f1']['min']*100:.2f}%, Max: {summary['macro_f1']['max']*100:.2f}%]")
    print(f"Weather -> Sensor False Alarm:     {summary['weather_to_sensor_false_alarm_rate']['mean']*100:.2f}% [Optimal: 0.00%]")
    print(f"Sensor -> Weather Error Rate:      {summary['sensor_to_weather_error_rate']['mean']*100:.2f}% [Optimal: 0.00%]")
    print(f"Mean Pipeline Latency:             {summary['mean_latency_ms']:.2f} ms / reading")
    print(f"P95 Pipeline Latency:              {summary['p95_latency_ms']:.2f} ms / reading")
    print("--------------------------------------------------")
    print("PER-CLASS METRICS (Reference Seed 42):")
    print(f"{'Class':<28} | {'Precision':<10} | {'Recall':<10} | {'F1':<10} | {'Support':<8}")
    print("-" * 75)
    for c, m in ref_run["per_class"].items():
        print(f"{c:<28} | {m['precision']*100:>8.2f}% | {m['recall']*100:>8.2f}% | {m['f1']*100:>8.2f}% | {m['support']:>8}")

    print("\nMULTICLASS CONFUSION MATRIX (Reference Seed 42):")
    header = "Pred -> | " + " | ".join([f"{c[:8]:>8}" for c in classes])
    print(header)
    print("-" * len(header))
    for i, c in enumerate(classes):
        row_str = f"{c[:7]:<7} | " + " | ".join([f"{cm[i, j]:>8}" for j in range(len(classes))])
        print(row_str)
    print("==================================================\n")

    # Export machine-readable JSON
    output_json_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"-> Saved benchmark results JSON to {output_json_path}")

    # Generate human-readable markdown BENCHMARK.md
    md_path = os.path.join(os.path.dirname(__file__), "BENCHMARK.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 📊 SkyGuard AI — Multiclass Ground-Truth Benchmark Report\n\n")
        f.write(f"> **Generated:** {summary['benchmark_timestamp']} UTC  \n")
        f.write(f"> **Evaluation Matrix:** {summary['total_seeds']} Random Seeds (`{summary['seeds_evaluated']}`)  \n")
        f.write(f"> **Dataset Size:** {summary['observations_per_seed']:,} Observations per Seed across 12 Automatic Weather Stations  \n\n")
        f.write("## 1. Multi-Seed Aggregate Performance Summary\n\n")
        f.write("| Metric | Mean | Std Dev | Min | Max | Target |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: |\n")
        f.write(f"| **Overall Accuracy** | **{summary['overall_accuracy']['mean']*100:.2f}%** | ±{summary['overall_accuracy']['std']*100:.2f}% | {summary['overall_accuracy']['min']*100:.2f}% | {summary['overall_accuracy']['max']*100:.2f}% | $\\ge 95.0\\%$ |\n")
        f.write(f"| **Macro Precision** | **{summary['macro_precision']['mean']*100:.2f}%** | ±{summary['macro_precision']['std']*100:.2f}% | {summary['macro_precision']['min']*100:.2f}% | {summary['macro_precision']['max']*100:.2f}% | $\\ge 85.0\\%$ |\n")
        f.write(f"| **Macro Recall** | **{summary['macro_recall']['mean']*100:.2f}%** | ±{summary['macro_recall']['std']*100:.2f}% | {summary['macro_recall']['min']*100:.2f}% | {summary['macro_recall']['max']*100:.2f}% | $\\ge 85.0\\%$ |\n")
        f.write(f"| **Macro F1-Score** | **{summary['macro_f1']['mean']*100:.2f}%** | ±{summary['macro_f1']['std']*100:.2f}% | {summary['macro_f1']['min']*100:.2f}% | {summary['macro_f1']['max']*100:.2f}% | $\\ge 85.0\\%$ |\n")
        f.write(f"| **Weather Event $\\to$ Sensor Fault Alarm** | **{summary['weather_to_sensor_false_alarm_rate']['mean']*100:.2f}%** | ±{summary['weather_to_sensor_false_alarm_rate']['std']*100:.2f}% | {summary['weather_to_sensor_false_alarm_rate']['min']*100:.2f}% | {summary['weather_to_sensor_false_alarm_rate']['max']*100:.2f}% | $\\le 2.0\\%$ |\n")
        f.write(f"| **Sensor Fault $\\to$ Weather Event Error** | **{summary['sensor_to_weather_error_rate']['mean']*100:.2f}%** | ±{summary['sensor_to_weather_error_rate']['std']*100:.2f}% | {summary['sensor_to_weather_error_rate']['min']*100:.2f}% | {summary['sensor_to_weather_error_rate']['max']*100:.2f}% | $\\le 2.0\\%$ |\n")
        f.write(f"| **Mean Latency per Reading** | **{summary['mean_latency_ms']:.2f} ms** | — | — | — | $< 25.0\\,\\text{{ms}}$ |\n")
        f.write(f"| **P95 Latency per Reading** | **{summary['p95_latency_ms']:.2f} ms** | — | — | — | $< 35.0\\,\\text{{ms}}$ |\n\n")

        f.write("## 2. Per-Class Ground-Truth Verification (Seed 42)\n\n")
        f.write("| Ground Truth Class | Support | Precision | Recall | F1-Score |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: |\n")
        for c, m in ref_run["per_class"].items():
            f.write(f"| **{c}** | {m['support']} | {m['precision']*100:.2f}% | {m['recall']*100:.2f}% | {m['f1']*100:.2f}% |\n")
        f.write("\n")

        f.write("## 3. Multiclass Confusion Matrix\n\n```\n")
        f.write(header + "\n")
        f.write("-" * len(header) + "\n")
        for i, c in enumerate(classes):
            row_str = f"{c[:7]:<7} | " + " | ".join([f"{cm[i, j]:>8}" for j in range(len(classes))])
            f.write(row_str + "\n")
        f.write("```\n")

    print(f"-> Generated human-readable report at {md_path}")
    return summary


if __name__ == "__main__":
    evaluate_benchmark()

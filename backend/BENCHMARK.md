# 📊 SkyGuard AI — Multiclass Ground-Truth Benchmark Report

> **Generated:** 2026-09-29T13:08:21.432199+00:00 UTC  
> **Evaluation Matrix:** 5 Random Seeds (`[42, 43, 44, 45, 46]`)  
> **Dataset Size:** 4,320 Observations per Seed across 12 Automatic Weather Stations  

## 1. Multi-Seed Aggregate Performance Summary

| Metric | Mean | Std Dev | Min | Max | Target |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Overall Accuracy** | **89.47%** | ±0.19% | 89.33% | 89.84% | $\ge 95.0\%$ |
| **Macro Precision** | **71.30%** | ±0.44% | 70.80% | 72.08% | $\ge 85.0\%$ |
| **Macro Recall** | **72.81%** | ±0.26% | 72.50% | 73.17% | $\ge 85.0\%$ |
| **Macro F1-Score** | **71.58%** | ±0.32% | 71.21% | 72.10% | $\ge 85.0\%$ |
| **Weather Event $\to$ Sensor Fault Alarm** | **17.56%** | ±1.59% | 15.00% | 19.44% | $\le 2.0\%$ |
| **Sensor Fault $\to$ Weather Event Error** | **0.37%** | ±0.07% | 0.31% | 0.46% | $\le 2.0\%$ |
| **Mean Latency per Reading** | **15.05 ms** | — | — | — | $< 25.0\,\text{ms}$ |
| **P95 Latency per Reading** | **16.00 ms** | — | — | — | $< 35.0\,\text{ms}$ |

## 2. Per-Class Ground-Truth Verification (Seed 42)

| Ground Truth Class | Support | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| **NORMAL** | 3485 | 95.37% | 94.58% | 94.97% |
| **REGIONAL_WEATHER_EVENT** | 180 | 35.39% | 35.00% | 35.20% |
| **SENSOR_SPIKE** | 94 | 51.20% | 68.09% | 58.45% |
| **SENSOR_FREEZE** | 96 | 100.00% | 96.88% | 98.41% |
| **CALIBRATION_DRIFT** | 84 | 29.27% | 42.86% | 34.78% |
| **COMMUNICATION_FAILURE** | 112 | 100.00% | 100.00% | 100.00% |
| **DATA_CORRUPTION** | 95 | 100.00% | 100.00% | 100.00% |
| **MULTIVARIATE_INCONSISTENCY** | 88 | 100.00% | 98.86% | 99.43% |
| **SPATIAL_INCONSISTENCY** | 86 | 28.57% | 16.28% | 20.74% |
| **INSUFFICIENT_EVIDENCE** | 0 | 0.00% | 0.00% | 0.00% |

## 3. Multiclass Confusion Matrix

```
Pred -> |   NORMAL | REGIONAL | SENSOR_S | SENSOR_F | CALIBRAT | COMMUNIC | DATA_COR | MULTIVAR | SPATIAL_ | INSUFFIC
---------------------------------------------------------------------------------------------------------------------
NORMAL  |     3296 |      112 |        2 |        0 |       51 |        0 |        0 |        0 |       22 |        2
REGIONA |       83 |       63 |        5 |        0 |       23 |        0 |        0 |        0 |        6 |        0
SENSOR_ |       19 |        3 |       64 |        0 |        8 |        0 |        0 |        0 |        0 |        0
SENSOR_ |        0 |        0 |        0 |       93 |        3 |        0 |        0 |        0 |        0 |        0
CALIBRA |       38 |        0 |        3 |        0 |       36 |        0 |        0 |        0 |        7 |        0
COMMUNI |        0 |        0 |        0 |        0 |        0 |      112 |        0 |        0 |        0 |        0
DATA_CO |        0 |        0 |        0 |        0 |        0 |        0 |       95 |        0 |        0 |        0
MULTIVA |        0 |        0 |        0 |        0 |        1 |        0 |        0 |       87 |        0 |        0
SPATIAL |       20 |        0 |       51 |        0 |        1 |        0 |        0 |        0 |       14 |        0
INSUFFI |        0 |        0 |        0 |        0 |        0 |        0 |        0 |        0 |        0 |        0
```

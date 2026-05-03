import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_engine import NexoraAI


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def mae(pairs):
    return mean(abs(actual - predicted) for actual, predicted in pairs)


def rmse(pairs):
    return mean((actual - predicted) ** 2 for actual, predicted in pairs) ** 0.5 if pairs else 0.0


def mape(pairs):
    valid = [(actual, predicted) for actual, predicted in pairs if actual != 0]
    if not valid:
        return 0.0
    return mean(abs((actual - predicted) / actual) for actual, predicted in valid) * 100


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def evaluate(
    dataset_path,
    history_window_days,
    min_history_samples,
    max_recommendations,
    high_trigger_multiplier,
    critical_trigger_multiplier,
    baseline_short_window,
    baseline_long_window,
    baseline_short_weight,
    baseline_long_weight,
):
    engine = NexoraAI(
        history_window_days=history_window_days,
        min_history_samples=min_history_samples,
        max_recommendations=max_recommendations,
        high_trigger_multiplier=high_trigger_multiplier,
        critical_trigger_multiplier=critical_trigger_multiplier,
        baseline_short_window=baseline_short_window,
        baseline_long_window=baseline_long_window,
        baseline_short_weight=baseline_short_weight,
        baseline_long_weight=baseline_long_weight,
    )

    rows = load_jsonl(dataset_path)
    community_pairs = []
    unit_pairs = []
    peak_labels = {}
    peak_predictions = {}
    recommendation_count = 0
    samples_evaluated = 0

    for row in rows:
        result = engine.run(row)
        current = result["community"]["current"]
        predicted = result["community"]["predicted"]
        peak_status = result["community"]["peak_status"]
        expected_peak = row.get("expected_peak_status")

        community_pairs.append((current, predicted))
        samples_evaluated += 1

        for unit in row.get("units", []):
            unit_id = unit["unit_id"]
            actual = unit.get("consumption_kwh", 0)
            predicted_unit = result["unit_predictions"].get(unit_id, 0.0)
            unit_pairs.append((actual, predicted_unit))

        if expected_peak:
            peak_labels[expected_peak] = peak_labels.get(expected_peak, 0) + 1
            peak_predictions[(expected_peak, peak_status)] = peak_predictions.get(
                (expected_peak, peak_status), 0
            ) + 1

        recommendation_count += len(result["recommendations"])

    return {
        "dataset_path": str(dataset_path),
        "samples_evaluated": samples_evaluated,
        "community_prediction": {
            "mae": round(mae(community_pairs), 3),
            "rmse": round(rmse(community_pairs), 3),
            "mape_percent": round(mape(community_pairs), 3),
        },
        "unit_prediction": {
            "mae": round(mae(unit_pairs), 3),
            "rmse": round(rmse(unit_pairs), 3),
            "mape_percent": round(mape(unit_pairs), 3),
        },
        "peak_label_distribution": peak_labels,
        "peak_confusion_counts": {
            f"{expected}->{predicted}": count
            for (expected, predicted), count in sorted(peak_predictions.items())
        },
        "recommendation_count": recommendation_count,
        "avg_recommendations_per_sample": round(recommendation_count / max(samples_evaluated, 1), 3),
        "config": {
            "history_window_days": history_window_days,
            "min_history_samples": min_history_samples,
            "max_recommendations": max_recommendations,
            "high_trigger_multiplier": high_trigger_multiplier,
            "critical_trigger_multiplier": critical_trigger_multiplier,
            "baseline_short_window": baseline_short_window,
            "baseline_long_window": baseline_long_window,
            "baseline_short_weight": baseline_short_weight,
            "baseline_long_weight": baseline_long_weight,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Replay dataset and evaluate Nexora AI.")
    parser.add_argument(
        "--dataset",
        default="evaluation/data/synthetic_hourly_7d.jsonl",
        help="Path to JSONL dataset",
    )
    parser.add_argument("--history-window-days", type=int, default=7)
    parser.add_argument("--min-history-samples", type=int, default=24)
    parser.add_argument("--max-recommendations", type=int, default=3)
    parser.add_argument("--high-trigger-multiplier", type=float, default=1.22)
    parser.add_argument("--critical-trigger-multiplier", type=float, default=1.45)
    parser.add_argument("--baseline-short-window", type=int, default=6)
    parser.add_argument("--baseline-long-window", type=int, default=24)
    parser.add_argument("--baseline-short-weight", type=float, default=0.6)
    parser.add_argument("--baseline-long-weight", type=float, default=0.4)
    args = parser.parse_args()

    report = evaluate(
        dataset_path=Path(args.dataset),
        history_window_days=args.history_window_days,
        min_history_samples=args.min_history_samples,
        max_recommendations=args.max_recommendations,
        high_trigger_multiplier=args.high_trigger_multiplier,
        critical_trigger_multiplier=args.critical_trigger_multiplier,
        baseline_short_window=args.baseline_short_window,
        baseline_long_window=args.baseline_long_window,
        baseline_short_weight=args.baseline_short_weight,
        baseline_long_weight=args.baseline_long_weight,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

# Evaluation

Folder ini berisi dataset sintetis dan script replay untuk mengukur performa dasar Nexora AI.

## Isi Folder

- `data/synthetic_hourly_1d.jsonl`: dataset sintetis per jam
- `data/synthetic_hourly_7d.jsonl`: dataset sintetis per jam untuk 7 hari
- `generate_synthetic_dataset.py`: generator dataset sintetis multi-hari
- `run_evaluation.py`: replay dataset dan hitung metrik evaluasi

## Format Dataset

Setiap baris adalah satu payload request `POST /analyze` dalam format JSONL.

Field tambahan evaluasi:

- `expected_peak_status`: label target untuk peak status pada sampel tersebut

Contoh:

```json
{
  "timestamp": "2026-05-01T20:00:00",
  "units": [...],
  "expected_peak_status": "critical"
}
```

## Menjalankan Evaluasi

```bash
python3 evaluation/run_evaluation.py
```

Contoh dengan konfigurasi lain:

```bash
python3 evaluation/run_evaluation.py \
  --dataset evaluation/data/synthetic_hourly_1d.jsonl \
  --history-window-days 7 \
  --min-history-samples 24 \
  --high-trigger-multiplier 1.22 \
  --critical-trigger-multiplier 1.45 \
  --baseline-short-window 6 \
  --baseline-long-window 24 \
  --baseline-short-weight 0.6 \
  --baseline-long-weight 0.4 \
  --max-recommendations 3
```

## Generate Dataset 7 Hari

```bash
python3 evaluation/generate_synthetic_dataset.py
```

Contoh output lain:

```bash
python3 evaluation/generate_synthetic_dataset.py \
  --days 14 \
  --output evaluation/data/synthetic_hourly_14d.jsonl
```

## Output

Script akan mengeluarkan JSON report berisi:

- `community_prediction.mae`
- `community_prediction.rmse`
- `community_prediction.mape_percent`
- `unit_prediction.mae`
- `unit_prediction.rmse`
- `unit_prediction.mape_percent`
- `peak_label_distribution`
- `peak_confusion_counts`
- `recommendation_count`
- `avg_recommendations_per_sample`
- `config.high_trigger_multiplier`
- `config.critical_trigger_multiplier`
- `config.baseline_short_window`
- `config.baseline_long_window`
- `config.baseline_short_weight`
- `config.baseline_long_weight`

## Catatan

- Dataset sintetis ini cocok untuk regression test dan sanity check.
- Ini bukan pengganti evaluasi dengan data lapangan.
- Untuk evaluasi real, Anda sebaiknya mengganti dataset ini dengan histori konsumsi komunitas yang benar-benar terjadi.

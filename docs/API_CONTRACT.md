# Nexora AI Service API Contract

## Overview

Service Nexora AI adalah HTTP JSON service yang membungkus engine di [ai_engine.py](/Users/macbook/Workdir/Personal/Projects/nexora/ai/ai_engine.py:1).

Karakteristik service:

- stateful selama process hidup
- history komunitas dan unit disimpan in-memory per `community_id`
- history memakai time window 7 hari terakhir secara default
- peak detection memakai mode warm-up sebelum histori cukup

## Configuration

Environment variable yang didukung:

- `NEXORA_HOST`
- `NEXORA_PORT`
- `NEXORA_HISTORY_WINDOW_DAYS`
- `NEXORA_MIN_HISTORY_SAMPLES`
- `NEXORA_MAX_RECOMMENDATIONS`
- `NEXORA_HIGH_TRIGGER_MULTIPLIER`
- `NEXORA_CRITICAL_TRIGGER_MULTIPLIER`
- `NEXORA_BASELINE_SHORT_WINDOW`
- `NEXORA_BASELINE_LONG_WINDOW`
- `NEXORA_BASELINE_SHORT_WEIGHT`
- `NEXORA_BASELINE_LONG_WEIGHT`

Default:

- host: `0.0.0.0`
- port: `8001`
- history window days: `7`
- min history samples: `24`
- max recommendations: `3`
- high trigger multiplier: `1.22`
- critical trigger multiplier: `1.45`
- baseline short window: `6`
- baseline long window: `24`
- baseline short weight: `0.6`
- baseline long weight: `0.4`

## Base Protocol

- Protocol: HTTP/1.1
- Request body untuk `POST`: `application/json`
- Response body: `application/json; charset=utf-8`

## Endpoints

### GET /health

Response:

```json
{
  "status": "ok"
}
```

### GET /state

Response:

```json
{
  "community_count": 2,
  "communities": {
    "COMMUNITY_A": {
      "community_id": "COMMUNITY_A",
      "history_window_days": 7,
      "min_history_samples": 24,
      "high_trigger_multiplier": 1.22,
      "critical_trigger_multiplier": 1.45,
      "baseline_short_window": 6,
      "baseline_long_window": 24,
      "baseline_short_weight": 0.6,
      "baseline_long_weight": 0.4,
      "community_history_count": 12,
      "tracked_units": ["U01", "U02"],
      "unit_history_count": {
        "U01": 12,
        "U02": 12
      },
      "fairness": {
        "U01": 2,
        "U02": 1
      },
      "max_recommendations": 3
    }
  }
}
```

Field:

- `community_count`: jumlah komunitas aktif yang sedang tersimpan di service
- `communities`: map state per `community_id`

Anda juga dapat meminta state satu komunitas:

`GET /state?community_id=COMMUNITY_A`

Response:

```json
{
  "exists": true,
  "community_id": "COMMUNITY_A",
  "history_window_days": 7,
  "min_history_samples": 24,
  "high_trigger_multiplier": 1.22,
  "critical_trigger_multiplier": 1.45,
  "baseline_short_window": 6,
  "baseline_long_window": 24,
  "baseline_short_weight": 0.6,
  "baseline_long_weight": 0.4,
  "community_history_count": 12,
  "tracked_units": ["U01", "U02"],
  "unit_history_count": {
    "U01": 12,
    "U02": 12
  },
  "fairness": {
    "U01": 2,
    "U02": 1
  },
  "max_recommendations": 3
}
```

### POST /analyze

Tujuan:

- memproses payload konsumsi baru
- menghitung kondisi komunitas
- membuat rekomendasi dan insight
- menyimpan data ke histori in-memory

Request body schema:

```json
{
  "community_id": "string, required",
  "timestamp": "string, required, ISO 8601",
  "units": [
    {
      "unit_id": "string, required",
      "tariff": "number, optional",
      "base_load_kwh": "number, optional",
      "consumption_kwh": "number, optional",
      "devices": {
        "<device_name>": {
          "state": "boolean, optional",
          "power": "number, optional",
          "controllable": "boolean, optional",
          "schedule": {
            "hours": ["integer hour 0-23, optional"]
          }
        }
      }
    }
  ]
}
```

Contoh request:

```json
{
  "community_id": "COMMUNITY_A",
  "timestamp": "2026-05-03T20:00:00",
  "units": [
    {
      "unit_id": "U01",
      "tariff": 1444,
      "base_load_kwh": 0.8,
      "consumption_kwh": 5.6,
      "devices": {
        "water_heater": {
          "state": true,
          "power": 1.5,
          "controllable": true,
          "schedule": {
            "hours": [5, 6, 7, 8]
          }
        },
        "smart_fan": {
          "state": true,
          "power": 0.4,
          "controllable": true
        }
      }
    },
    {
      "unit_id": "U02",
      "tariff": 1444,
      "base_load_kwh": 0.7,
      "consumption_kwh": 6.2,
      "devices": {
        "washing_machine": {
          "state": true,
          "power": 0.8,
          "controllable": true,
          "schedule": {
            "hours": [8, 9, 10, 11, 12, 13, 14, 15]
          }
        }
      }
    }
  ]
}
```

Contoh response:

```json
{
  "status": "success",
  "community_id": "COMMUNITY_A",
  "result": {
    "community": {
      "current": 11.8,
      "predicted": 10.9,
      "baseline": 10.9,
      "threshold": 10.9,
      "high_trigger": 11.99,
      "critical_trigger": 13.63,
      "peak_status": "warming_up",
      "history_ready": false,
      "history_samples": 12,
      "min_history_samples": 24,
      "warmup_remaining_samples": 12,
      "co2": 10.03
    },
    "unit_predictions": {
      "U01": 5.1,
      "U02": 5.8
    },
    "recommendations": [
      {
        "unit_id": "U02",
        "device": "washing_machine",
        "action": "turn_off",
        "estimated_reduction_kwh": 0.8,
        "saving": 1155.2,
        "co2_reduction": 0.68,
        "priority_score": 4335.853,
        "fairness_count": 2,
        "unit_baseline_kwh": 5.76,
        "reasons": [
          "Histori komunitas belum cukup untuk deteksi peak yang stabil",
          "Unit ini menyumbang 35.0% dari beban komunitas saat ini",
          "washing_machine termasuk perangkat boros energi",
          "Estimasi hemat Rp 1155.2",
          "Estimasi pengurangan CO2 0.68 kg"
        ]
      }
    ],
    "insights": [],
    "fairness": {
      "U01": 2,
      "U02": 3
    }
  },
  "state": {
    "exists": true,
    "community_id": "COMMUNITY_A",
    "history_window_days": 7,
    "min_history_samples": 24,
    "high_trigger_multiplier": 1.22,
    "critical_trigger_multiplier": 1.45,
    "baseline_short_window": 6,
    "baseline_long_window": 24,
    "baseline_short_weight": 0.6,
    "baseline_long_weight": 0.4,
    "community_history_count": 12,
    "tracked_units": ["U01", "U02"],
    "unit_history_count": {
      "U01": 12,
      "U02": 12
    },
    "fairness": {
      "U01": 2,
      "U02": 3
    },
    "max_recommendations": 3
  }
}
```

Field `result.community`:

- `current`: total konsumsi komunitas saat ini
- `predicted`: prediksi komunitas dari histori aktif
- `baseline`: baseline komunitas untuk peak detection
- `threshold`: alias kompatibilitas untuk `baseline`
- `high_trigger`: batas untuk status `high`
- `critical_trigger`: batas untuk status `critical`
- `peak_status`: `warming_up`, `normal`, `high`, atau `critical`
- `history_ready`: readiness peak detection
- `history_samples`: jumlah sampel komunitas aktif
- `min_history_samples`: minimum sampel yang dibutuhkan
- `warmup_remaining_samples`: sisa sampel warm-up
- `co2`: estimasi emisi komunitas

Field `result.recommendations[]`:

- `unit_id`
- `device`
- `action`
- `estimated_reduction_kwh`
- `saving`
- `co2_reduction`
- `priority_score`
- `fairness_count`
- `unit_baseline_kwh`
- `reasons`

Aturan action:

- `turn_off`: device aktif di luar jadwal
- `reduce`: device sebaiknya dikurangi karena komunitas `high/critical` dan unit relevan terhadap lonjakan beban
  - saat `critical`: unit dianggap relevan jika deviasi dari baseline >= 10% atau kontribusi komunitas >= 30%
  - saat `high`: unit dianggap relevan jika deviasi dari baseline >= 20% atau kontribusi komunitas >= 35%

### POST /reset

Response:

```json
{
  "status": "reset"
}
```

Untuk reset satu komunitas saja:

Request:

```json
{
  "community_id": "COMMUNITY_A"
}
```

Response:

```json
{
  "status": "reset",
  "community_id": "COMMUNITY_A"
}
```

Jika request body kosong, service akan me-reset seluruh komunitas:

```json
{
  "status": "reset_all"
}
```

## Error Contract

### 400 Bad Request

Contoh:

```json
{
  "error": "Request body must be valid JSON"
}
```

Atau:

```json
{
  "error": "Missing required field: community_id"
}
```

### 404 Not Found

Contoh:

```json
{
  "error": "Not found"
}
```

### 500 Internal Server Error

Contoh:

```json
{
  "error": "Internal error: <message>"
}
```

## Behavioral Notes

- History hanya memakai data dalam window aktif, default 7 hari terakhir.
- Jika update datang 1 jam sekali, window 7 hari kira-kira berarti 168 sampel aktif.
- Jika histori komunitas belum mencapai `min_history_samples`, status akan `warming_up`.
- Seluruh histori, fairness, dan baseline diisolasi per `community_id`.
- Trigger peak default saat ini:
  - `high` jika `current > baseline * 1.22`
  - `critical` jika `current > baseline * 1.45` dan sampel komunitas sebelumnya sudah di atas `high_trigger`
- Baseline komunitas default adalah kombinasi:
  - 60% rata-rata 6 sampel terakhir
  - 40% rata-rata 24 sampel terakhir
- Saat `warming_up`, rule deterministik seperti `turn_off` karena di luar jadwal tetap bisa muncul.
- History hilang jika process restart, karena belum ada persistence database.

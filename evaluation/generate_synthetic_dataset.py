import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


UNITS = [
    {
        "unit_id": "U01",
        "tariff": 1444,
        "base_load_kwh": 0.8,
    },
    {
        "unit_id": "U02",
        "tariff": 1444,
        "base_load_kwh": 0.7,
    },
    {
        "unit_id": "U03",
        "tariff": 1444,
        "base_load_kwh": 0.9,
    },
]


def device_profile(unit_id, hour, day_index):
    evening = 18 <= hour <= 22
    morning = 5 <= hour <= 8
    washing_window = 8 <= hour <= 15
    cooking_window = hour in [11, 12, 13, 17]
    weekend_like = day_index % 7 in [5, 6]

    if unit_id == "U01":
        return {
            "ac_bedroom": {
                "state": evening,
                "power": 1.2,
                "controllable": True,
                "schedule": {"hours": [18, 19, 20, 21, 22]},
            },
            "water_heater": {
                "state": morning or (day_index % 5 == 0 and hour == 20),
                "power": 1.5,
                "controllable": True,
                "schedule": {"hours": [5, 6, 7, 8]},
            },
            "smart_fan": {
                "state": True,
                "power": 0.4,
                "controllable": True,
            },
        }

    if unit_id == "U02":
        return {
            "ac_living_room": {
                "state": evening,
                "power": 1.4,
                "controllable": True,
                "schedule": {"hours": [18, 19, 20, 21, 22]},
            },
            "washing_machine": {
                "state": washing_window and (weekend_like or hour in [8, 9, 10, 11]),
                "power": 0.8,
                "controllable": True,
                "schedule": {"hours": [8, 9, 10, 11, 12, 13, 14, 15]},
            },
            "tv_guest_room": {
                "state": evening,
                "power": 0.2,
                "controllable": True,
            },
        }

    return {
        "ac_master": {
            "state": evening,
            "power": 1.3,
            "controllable": True,
            "schedule": {"hours": [18, 19, 20, 21, 22]},
        },
        "oven": {
            "state": cooking_window and (weekend_like or hour in [12, 17]),
            "power": 1.8,
            "controllable": True,
            "schedule": {"hours": [11, 12, 13, 17]},
        },
        "air_purifier": {
            "state": True,
            "power": 0.3,
            "controllable": False,
        },
    }


def base_consumption(hour, day_index):
    if 0 <= hour <= 4:
        return [2.1, 2.0, 2.2]
    if 5 <= hour <= 7:
        return [3.4, 2.2, 2.3]
    if 8 <= hour <= 10:
        return [2.8, 3.2, 2.9]
    if 11 <= hour <= 13:
        return [3.0, 3.1, 4.7]
    if 14 <= hour <= 17:
        return [2.9, 3.0, 3.0]
    if 18 <= hour <= 22:
        return [4.8, 5.2, 4.9]
    return [2.5, 2.3, 2.4]


def day_adjustment(day_index):
    pattern = [0.0, 0.1, -0.05, 0.15, -0.1, 0.35, 0.25]
    return pattern[day_index % len(pattern)]


def spike_adjustment(hour, day_index):
    if hour == 17 and day_index in [1, 3]:
        return [0.3, 0.2, 1.8], "high"
    if hour == 19 and day_index in [2, 5]:
        return [0.8, 1.0, 0.9], "critical"
    if hour == 20 and day_index in [4, 6]:
        return [0.9, 1.1, 1.0], "critical"
    if hour in [18, 21, 22] and day_index in [2, 4, 6]:
        return [0.4, 0.5, 0.4], "high"
    return [0.0, 0.0, 0.0], "normal"


def expected_peak(hour, day_index):
    _, label = spike_adjustment(hour, day_index)
    return label


def build_row(timestamp, day_index):
    hour = timestamp.hour
    base = base_consumption(hour, day_index)
    adj = day_adjustment(day_index)
    spike, expected = spike_adjustment(hour, day_index)
    units = []

    for idx, unit in enumerate(UNITS):
        consumption = round(base[idx] + adj + spike[idx], 2)
        units.append(
            {
                "unit_id": unit["unit_id"],
                "tariff": unit["tariff"],
                "base_load_kwh": unit["base_load_kwh"],
                "consumption_kwh": consumption,
                "devices": device_profile(unit["unit_id"], hour, day_index),
            }
        )

    return {
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "units": units,
        "expected_peak_status": expected,
    }


def generate(start, days):
    rows = []
    current = start
    for day_index in range(days):
        for hour in range(24):
            timestamp = current + timedelta(days=day_index, hours=hour)
            rows.append(build_row(timestamp, day_index))
    return rows


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic hourly dataset for Nexora AI.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--start", default="2026-05-01T00:00:00")
    parser.add_argument(
        "--output",
        default="evaluation/data/synthetic_hourly_7d.jsonl",
        help="Output JSONL path",
    )
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start)
    rows = generate(start, args.days)
    write_jsonl(Path(args.output), rows)
    print(
        json.dumps(
            {
                "output": args.output,
                "days": args.days,
                "rows": len(rows),
                "start": args.start,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

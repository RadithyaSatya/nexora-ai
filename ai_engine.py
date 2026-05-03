from collections import deque, defaultdict
from datetime import datetime, timedelta

CO2_FACTOR = 0.85  # kg CO2e per kWh


class NexoraAI:
    def __init__(
        self,
        history_window_days=7,
        min_history_samples=24,
        max_recommendations=3,
        high_trigger_multiplier=1.22,
        critical_trigger_multiplier=1.45,
        baseline_short_window=6,
        baseline_long_window=24,
        baseline_short_weight=0.6,
        baseline_long_weight=0.4,
    ):
        self.history_window_days = history_window_days
        self.min_history_samples = min_history_samples
        self.high_trigger_multiplier = high_trigger_multiplier
        self.critical_trigger_multiplier = critical_trigger_multiplier
        self.baseline_short_window = baseline_short_window
        self.baseline_long_window = baseline_long_window
        self.baseline_short_weight = baseline_short_weight
        self.baseline_long_weight = baseline_long_weight
        self.history_window = timedelta(days=history_window_days)
        self.community_history = deque()
        self.unit_history = defaultdict(deque)

        # fairness memory: makin sering unit kena rekomendasi, makin kecil prioritasnya
        self.unit_target_count = defaultdict(int)

        self.max_recommendations = max_recommendations

    # =========================
    # BASIC CALCULATION
    # =========================

    def aggregate(self, units):
        return round(sum(u.get("consumption_kwh", 0) for u in units), 3)

    def cost(self, kwh, tariff):
        return round(kwh * tariff, 2)

    def co2(self, kwh):
        return round(kwh * CO2_FACTOR, 2)

    # =========================
    # HISTORY & PREDICTION
    # =========================

    def history_cutoff(self, now):
        return now - self.history_window

    def prune_history(self, now):
        cutoff = self.history_cutoff(now)

        while self.community_history and self.community_history[0][0] < cutoff:
            self.community_history.popleft()

        empty_units = []
        for unit_id, history in self.unit_history.items():
            while history and history[0][0] < cutoff:
                history.popleft()

            if not history:
                empty_units.append(unit_id)

        for unit_id in empty_units:
            del self.unit_history[unit_id]

    def update_history(self, now, units, community_current):
        for unit in units:
            self.unit_history[unit["unit_id"]].append(
                (now, unit.get("consumption_kwh", 0))
            )

        self.community_history.append((now, community_current))
        self.prune_history(now)

    def history_values(self, history):
        return [value for _, value in history]

    def predict_from_history(self, history):
        if not history:
            return 0.0

        values = self.history_values(history)

        if len(values) < 3:
            return round(sum(values) / len(values), 3)

        short_term = values[-3:]
        medium_term = values[-min(12, len(values)):]

        short_avg = sum(short_term) / len(short_term)
        medium_avg = sum(medium_term) / len(medium_term)

        return round((short_avg * 0.7) + (medium_avg * 0.3), 3)

    def predict_unit(self, unit_id):
        return self.predict_from_history(self.unit_history[unit_id])

    def predict_community(self):
        return self.predict_from_history(self.community_history)

    def baseline_gap(self, current, baseline):
        return round(max(0, current - baseline), 3)

    def deviation_ratio(self, current, baseline):
        if baseline <= 0:
            return 0.0 if current <= 0 else 1.0

        return round(max(0, (current - baseline) / baseline), 3)

    def community_share_ratio(self, consumption, community_current):
        return consumption / max(community_current, 0.001)

    # =========================
    # THRESHOLD & PEAK DETECTION
    # =========================

    def community_baseline(self, predicted):
        if not self.community_history:
            return 0.0

        values = self.history_values(self.community_history)
        short_values = values[-min(self.baseline_short_window, len(values)):]
        long_values = values[-min(self.baseline_long_window, len(values)):]

        short_avg = sum(short_values) / len(short_values)
        long_avg = sum(long_values) / len(long_values)

        return round(
            (short_avg * self.baseline_short_weight)
            + (long_avg * self.baseline_long_weight),
            3,
        )

    def peak_triggers(self, baseline):
        if baseline <= 0:
            return {
                "high": 0.0,
                "critical": 0.0,
            }

        return {
            "high": round(baseline * self.high_trigger_multiplier, 3),
            "critical": round(baseline * self.critical_trigger_multiplier, 3),
        }

    def history_readiness(self):
        samples = len(self.community_history)
        history_ready = samples >= self.min_history_samples
        return {
            "history_ready": history_ready,
            "history_samples": samples,
            "min_history_samples": self.min_history_samples,
            "warmup_remaining_samples": max(0, self.min_history_samples - samples),
        }

    def detect_peak(self, current, triggers, readiness):
        if not readiness["history_ready"]:
            return "warming_up"

        previous_values = self.history_values(self.community_history)
        previous_community = previous_values[-1] if previous_values else 0.0

        if triggers["critical"] <= 0:
            return "normal"

        if current > triggers["critical"] and previous_community > triggers["high"]:
            return "critical"

        if current > triggers["high"]:
            return "high"

        return "normal"

    # =========================
    # DEVICE & SCHEDULE LOGIC
    # =========================

    def resolve_schedule(self, device, hour):
        schedule = device.get("schedule")
        if not schedule:
            return None, None

        if isinstance(schedule, list):
            return schedule, None

        active_hours = schedule.get("hours")
        if active_hours is None:
            active_hours = schedule.get("normal", [])

        if active_hours and hour not in active_hours:
            return active_hours, "outside_schedule"

        return active_hours, None

    def evaluate_schedule(self, device, hour):
        _, status = self.resolve_schedule(device, hour)
        return status

    def evaluate_controllable_device(self, name, device, hour, peak_status):
        if not device.get("controllable", False):
            return None

        schedule_result = self.evaluate_schedule(device, hour)
        if schedule_result == "outside_schedule":
            return "turn_off"

        if peak_status in ["high", "critical"] and device.get("power", 0) > 0.5:
            return "reduce"

        return None

    def generate_non_controllable_insight(self, unit_id, name, device, hour):
        if device.get("controllable", False):
            return None

        _, schedule_result = self.resolve_schedule(device, hour)

        if device.get("state") and schedule_result == "outside_schedule":
            return {
                "unit_id": unit_id,
                "type": "insight",
                "device": name,
                "message": f"{name} menyala di luar jadwal normal",
            }

        return None

    # =========================
    # PRIORITY SCORING & FAIRNESS
    # =========================

    def priority_score(self, unit, community_current, unit_baseline):
        unit_id = unit["unit_id"]
        consumption = unit.get("consumption_kwh", 0)
        tariff = unit.get("tariff", 1444)

        cost_impact = consumption * tariff
        deviation_factor = 1 + min(2.0, self.deviation_ratio(consumption, unit_baseline))
        community_share = consumption / max(community_current, 0.001)
        share_factor = 1 + community_share
        fairness_penalty = 1 + self.unit_target_count[unit_id]

        return round((cost_impact * deviation_factor * share_factor) / fairness_penalty, 3)

    def sort_units_by_priority(self, units, community_current, unit_baselines):
        return sorted(
            units,
            key=lambda u: self.priority_score(
                u,
                community_current,
                unit_baselines.get(u["unit_id"], 0.0),
            ),
            reverse=True,
        )

    def should_reduce_unit(self, unit, community_current, unit_baseline, peak_status):
        if peak_status not in ["high", "critical"]:
            return False

        consumption = unit.get("consumption_kwh", 0)
        deviation = self.deviation_ratio(consumption, unit_baseline)
        community_share = self.community_share_ratio(consumption, community_current)

        if peak_status == "critical":
            return deviation >= 0.1 or community_share >= 0.3

        return deviation >= 0.2 or community_share >= 0.35

    # =========================
    # RECOMMENDATION
    # =========================

    def controllable_load(self, unit):
        base = unit.get("base_load_kwh", 0)
        total = unit.get("consumption_kwh", 0)
        return max(0, round(total - base, 3))

    def build_reasons(
        self,
        unit,
        device_name,
        device,
        peak_status,
        community_current,
        unit_baseline,
        saving,
        co2,
    ):
        reasons = []
        consumption = unit.get("consumption_kwh", 0)

        if peak_status == "critical":
            reasons.append("Beban listrik komunitas sedang tinggi")

        if peak_status == "high":
            reasons.append("Beban listrik komunitas mulai tinggi")

        if peak_status == "warming_up":
            reasons.append("Histori komunitas belum cukup untuk deteksi peak yang stabil")

        if unit_baseline > 0:
            deviation_pct = self.deviation_ratio(consumption, unit_baseline) * 100
            if deviation_pct >= 10:
                reasons.append(
                    f"Konsumsi unit {round(deviation_pct, 1)}% di atas baseline historisnya"
                )

        community_share_pct = round(self.community_share_ratio(consumption, community_current) * 100, 1)
        if community_share_pct >= 30:
            reasons.append(
                f"Unit ini menyumbang {community_share_pct}% dari beban komunitas saat ini"
            )

        if device.get("power", 0) > 0.5:
            reasons.append(f"{device_name} termasuk perangkat boros energi")

        reasons.append(f"Estimasi hemat Rp {saving}")
        reasons.append(f"Estimasi pengurangan CO2 {co2} kg")

        return reasons

    def recommend(self, units, peak_status, hour, community, unit_baselines):
        recommendations = []
        insights = []

        if not units:
            return recommendations, insights

        community_current = community["current"]
        sorted_units = self.sort_units_by_priority(units, community_current, unit_baselines)

        for unit in sorted_units:
            unit_id = unit["unit_id"]
            tariff = unit.get("tariff", 1444)
            max_reduction = self.controllable_load(unit)
            unit_baseline = unit_baselines.get(unit_id, 0.0)
            eligible_for_reduce = self.should_reduce_unit(
                unit,
                community_current,
                unit_baseline,
                peak_status,
            )

            if max_reduction <= 0:
                continue

            # insight tetap dicek untuk semua device
            for device_name, device in unit.get("devices", {}).items():
                insight = self.generate_non_controllable_insight(unit_id, device_name, device, hour)
                if insight:
                    insights.append(insight)

            # recommendation hanya untuk controllable device yang sedang ON
            candidates = []

            for device_name, device in unit.get("devices", {}).items():
                if not device.get("state", False):
                    continue

                action = self.evaluate_controllable_device(
                    device_name,
                    device,
                    hour,
                    peak_status,
                )

                if action == "reduce" and not eligible_for_reduce:
                    continue

                if not action:
                    continue

                if not device.get("controllable", False):
                    continue

                power = device.get("power", 0.3)

                candidates.append({
                    "device_name": device_name,
                    "device": device,
                    "action": action,
                    "power": power,
                })

            if not candidates:
                continue

            # pilih device paling besar dampaknya
            best = sorted(candidates, key=lambda x: x["power"], reverse=True)[0]
            device_name = best["device_name"]
            device = best["device"]
            action = best["action"]

            reduction = min(best["power"], max_reduction)
            saving = self.cost(reduction, tariff)
            co2 = self.co2(reduction)

            rec = {
                "unit_id": unit_id,
                "device": device_name,
                "action": action,
                "estimated_reduction_kwh": round(reduction, 3),
                "saving": saving,
                "co2_reduction": co2,
                "priority_score": self.priority_score(unit, community_current, unit_baseline),
                "fairness_count": self.unit_target_count[unit_id],
                "unit_baseline_kwh": round(unit_baseline, 2),
                "reasons": self.build_reasons(
                    unit=unit,
                    device_name=device_name,
                    device=device,
                    peak_status=peak_status,
                    community_current=community_current,
                    unit_baseline=unit_baseline,
                    saving=saving,
                    co2=co2,
                ),
            }

            recommendations.append(rec)

            # fairness update: unit ini sudah kena rekomendasi
            self.unit_target_count[unit_id] += 1

            if len(recommendations) >= self.max_recommendations:
                break

        return recommendations, insights

    # =========================
    # MAIN RUN
    # =========================

    def run(self, payload):
        now = datetime.fromisoformat(payload["timestamp"])
        units = payload.get("units", [])
        hour = now.hour
        self.prune_history(now)

        current = self.aggregate(units)
        predicted = self.predict_community()
        baseline = self.community_baseline(predicted)
        triggers = self.peak_triggers(baseline)
        readiness = self.history_readiness()
        peak_status = self.detect_peak(current, triggers, readiness)

        unit_predictions = {
            unit["unit_id"]: round(self.predict_unit(unit["unit_id"]), 2)
            for unit in units
        }

        community = {
            "current": round(current, 2),
            "predicted": round(predicted, 2),
            "baseline": round(baseline, 2),
            "threshold": round(baseline, 2),
            "high_trigger": round(triggers["high"], 2),
            "critical_trigger": round(triggers["critical"], 2),
            "peak_status": peak_status,
            "history_ready": readiness["history_ready"],
            "history_samples": readiness["history_samples"],
            "min_history_samples": readiness["min_history_samples"],
            "warmup_remaining_samples": readiness["warmup_remaining_samples"],
            "co2": self.co2(current),
        }

        recommendations, insights = self.recommend(
            units=units,
            peak_status=peak_status,
            hour=hour,
            community=community,
            unit_baselines=unit_predictions,
        )

        self.update_history(now, units, current)

        return {
            "community": community,
            "unit_predictions": unit_predictions,
            "recommendations": recommendations,
            "insights": insights,
            "fairness": dict(self.unit_target_count),
        }

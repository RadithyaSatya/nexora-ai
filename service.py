import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ai_engine import NexoraAI


HOST = os.getenv("NEXORA_HOST", "0.0.0.0")
PORT = int(os.getenv("NEXORA_PORT", "8001"))
HISTORY_WINDOW_DAYS = int(os.getenv("NEXORA_HISTORY_WINDOW_DAYS", "7"))
MIN_HISTORY_SAMPLES = int(os.getenv("NEXORA_MIN_HISTORY_SAMPLES", "24"))
MAX_RECOMMENDATIONS = int(os.getenv("NEXORA_MAX_RECOMMENDATIONS", "3"))
HIGH_TRIGGER_MULTIPLIER = float(os.getenv("NEXORA_HIGH_TRIGGER_MULTIPLIER", "1.22"))
CRITICAL_TRIGGER_MULTIPLIER = float(os.getenv("NEXORA_CRITICAL_TRIGGER_MULTIPLIER", "1.45"))
BASELINE_SHORT_WINDOW = int(os.getenv("NEXORA_BASELINE_SHORT_WINDOW", "6"))
BASELINE_LONG_WINDOW = int(os.getenv("NEXORA_BASELINE_LONG_WINDOW", "24"))
BASELINE_SHORT_WEIGHT = float(os.getenv("NEXORA_BASELINE_SHORT_WEIGHT", "0.6"))
BASELINE_LONG_WEIGHT = float(os.getenv("NEXORA_BASELINE_LONG_WEIGHT", "0.4"))

AI_ENGINES = {}
AI_LOCK = threading.Lock()


def build_engine():
    return NexoraAI(
        history_window_days=HISTORY_WINDOW_DAYS,
        min_history_samples=MIN_HISTORY_SAMPLES,
        max_recommendations=MAX_RECOMMENDATIONS,
        high_trigger_multiplier=HIGH_TRIGGER_MULTIPLIER,
        critical_trigger_multiplier=CRITICAL_TRIGGER_MULTIPLIER,
        baseline_short_window=BASELINE_SHORT_WINDOW,
        baseline_long_window=BASELINE_LONG_WINDOW,
        baseline_short_weight=BASELINE_SHORT_WEIGHT,
        baseline_long_weight=BASELINE_LONG_WEIGHT,
    )


def get_engine(community_id):
    if community_id not in AI_ENGINES:
        AI_ENGINES[community_id] = build_engine()
    return AI_ENGINES[community_id]


def engine_snapshot(community_id, engine):
    return {
        "community_id": community_id,
        "history_window_days": engine.history_window_days,
        "min_history_samples": engine.min_history_samples,
        "high_trigger_multiplier": engine.high_trigger_multiplier,
        "critical_trigger_multiplier": engine.critical_trigger_multiplier,
        "baseline_short_window": engine.baseline_short_window,
        "baseline_long_window": engine.baseline_long_window,
        "baseline_short_weight": engine.baseline_short_weight,
        "baseline_long_weight": engine.baseline_long_weight,
        "community_history_count": len(engine.community_history),
        "tracked_units": sorted(engine.unit_history.keys()),
        "unit_history_count": {
            unit_id: len(history)
            for unit_id, history in engine.unit_history.items()
        },
        "fairness": dict(engine.unit_target_count),
        "max_recommendations": engine.max_recommendations,
    }


def json_response(handler, status_code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler):
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        raise ValueError("Request body is required")

    raw_body = handler.rfile.read(content_length)
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON") from exc


def snapshot_state(community_id=None):
    with AI_LOCK:
        if community_id:
            engine = AI_ENGINES.get(community_id)
            if not engine:
                return {
                    "community_id": community_id,
                    "exists": False,
                }
            return {
                "exists": True,
                **engine_snapshot(community_id, engine),
            }

        return {
            "community_count": len(AI_ENGINES),
            "communities": {
                cid: engine_snapshot(cid, engine)
                for cid, engine in sorted(AI_ENGINES.items())
            },
        }


def reset_state(community_id=None):
    with AI_LOCK:
        if community_id:
            AI_ENGINES.pop(community_id, None)
            return
        AI_ENGINES.clear()


class NexoraRequestHandler(BaseHTTPRequestHandler):
    server_version = "NexoraAIService/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/health":
            json_response(self, 200, {"status": "ok"})
            return

        if parsed.path == "/state":
            community_id = query.get("community_id", [None])[0]
            json_response(self, 200, snapshot_state(community_id))
            return

        json_response(
            self,
            404,
            {
                "error": "Not found",
                "available_endpoints": [
                    "GET /health",
                    "GET /state",
                    "POST /analyze",
                    "POST /reset",
                ],
            },
        )

    def do_POST(self):
        if self.path == "/analyze":
            self.handle_analyze()
            return

        if self.path == "/reset":
            self.handle_reset()
            return

        json_response(self, 404, {"error": "Not found"})

    def handle_analyze(self):
        try:
            payload = read_json(self)
        except ValueError as exc:
            json_response(self, 400, {"error": str(exc)})
            return

        community_id = payload.get("community_id")
        if not community_id:
            json_response(self, 400, {"error": "Missing required field: community_id"})
            return

        try:
            with AI_LOCK:
                engine = get_engine(community_id)
                result = engine.run(payload)
        except KeyError as exc:
            json_response(self, 400, {"error": f"Missing required field: {exc.args[0]}"})
            return
        except Exception as exc:
            json_response(self, 500, {"error": f"Internal error: {str(exc)}"})
            return

        json_response(
            self,
            200,
            {
                "status": "success",
                "community_id": community_id,
                "result": result,
                "state": snapshot_state(community_id),
            },
        )

    def handle_reset(self):
        try:
            payload = read_json(self)
        except ValueError:
            payload = {}

        community_id = payload.get("community_id")
        reset_state(community_id)
        if community_id:
            json_response(self, 200, {"status": "reset", "community_id": community_id})
            return
        json_response(self, 200, {"status": "reset_all"})

    def log_message(self, format, *args):
        return


def run():
    server = ThreadingHTTPServer((HOST, PORT), NexoraRequestHandler)
    print(f"Nexora AI service running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()

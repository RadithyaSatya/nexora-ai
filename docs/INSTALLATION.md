# Installation

## Requirements

- Python 3.8 atau lebih baru
- `pip` opsional

## Project Structure

- `ai_engine.py`: core engine analitik dan rekomendasi
- `service.py`: HTTP service wrapper untuk `NexoraAI`
- `requirements.txt`: dependency Python

## Install

Project ini saat ini hanya memakai Python standard library, jadi tidak ada package eksternal yang wajib di-install.

Jika ingin menjalankan dengan virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Service

Jalankan service:

```bash
python3 service.py
```

Default address:

```text
http://0.0.0.0:8001
```

## Docker

Build image:

```bash
docker build -t nexora-ai .
```

Run container:

```bash
docker run -d \
  --name nexora-ai \
  -p 8001:8001 \
  -e NEXORA_PORT=8001 \
  -e NEXORA_HISTORY_WINDOW_DAYS=7 \
  -e NEXORA_MIN_HISTORY_SAMPLES=24 \
  -e NEXORA_HIGH_TRIGGER_MULTIPLIER=1.22 \
  -e NEXORA_CRITICAL_TRIGGER_MULTIPLIER=1.45 \
  -e NEXORA_BASELINE_SHORT_WINDOW=6 \
  -e NEXORA_BASELINE_LONG_WINDOW=24 \
  -e NEXORA_BASELINE_SHORT_WEIGHT=0.6 \
  -e NEXORA_BASELINE_LONG_WEIGHT=0.4 \
  nexora-ai
```

Container default command:

```bash
python service.py
```

## Docker Compose

Project ini menyediakan dua mode Docker Compose.

### 1. Dev

Mode ini tidak memakai Nginx. Service AI langsung expose ke host/port yang Anda tentukan.

Siapkan env:

```bash
cp .env.dev.example .env.dev
```

Contoh:

```env
APP_PORT=8001
HISTORY_WINDOW_DAYS=7
MIN_HISTORY_SAMPLES=24
MAX_RECOMMENDATIONS=3
HIGH_TRIGGER_MULTIPLIER=1.22
CRITICAL_TRIGGER_MULTIPLIER=1.45
BASELINE_SHORT_WINDOW=6
BASELINE_LONG_WINDOW=24
BASELINE_SHORT_WEIGHT=0.6
BASELINE_LONG_WEIGHT=0.4
```

Jalankan:

```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

Akses:

```text
http://127.0.0.1:8001
```

Mode dev memang dibuka ke host publik pada port `APP_PORT`, jadi service bisa di-hit dari luar VPS melalui `http://IP_VPS:8001`.

### 2. Prod / VPS

Mode ini tidak menjalankan Nginx di dalam compose. Service AI dibind ke host lokal VPS, lalu Nginx host yang sudah ada melakukan reverse proxy berdasarkan subdomain.

Siapkan env:

```bash
cp .env.prod.example .env.prod
```

Contoh:

```env
APP_DOMAIN=ai.example.com
APP_PORT=8001
HISTORY_WINDOW_DAYS=7
MIN_HISTORY_SAMPLES=24
MAX_RECOMMENDATIONS=3
HIGH_TRIGGER_MULTIPLIER=1.22
CRITICAL_TRIGGER_MULTIPLIER=1.45
BASELINE_SHORT_WINDOW=6
BASELINE_LONG_WINDOW=24
BASELINE_SHORT_WEIGHT=0.6
BASELINE_LONG_WEIGHT=0.4
```

Jalankan:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Akses publik:

```text
http://ai.example.com
```

Service internal yang diproxy oleh Nginx host:

```text
http://127.0.0.1:8001
```

Contoh config Nginx host:

```text
nginx/ai.prod.conf.example
```

### Stop dan Logs

Dev:

```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml down
docker compose --env-file .env.dev -f docker-compose.dev.yml logs -f
```

Prod:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f
```

## Environment Variables

- `APP_PORT`
- `APP_DOMAIN` hanya untuk mode prod
- `HISTORY_WINDOW_DAYS`
- `MIN_HISTORY_SAMPLES`
- `MAX_RECOMMENDATIONS`
- `HIGH_TRIGGER_MULTIPLIER`
- `CRITICAL_TRIGGER_MULTIPLIER`
- `BASELINE_SHORT_WINDOW`
- `BASELINE_LONG_WINDOW`
- `BASELINE_SHORT_WEIGHT`
- `BASELINE_LONG_WEIGHT`

Contoh:

```bash
APP_PORT=8010 \
APP_DOMAIN=ai.example.com \
HISTORY_WINDOW_DAYS=7 \
MIN_HISTORY_SAMPLES=24 \
MAX_RECOMMENDATIONS=3 \
HIGH_TRIGGER_MULTIPLIER=1.22 \
CRITICAL_TRIGGER_MULTIPLIER=1.45 \
BASELINE_SHORT_WINDOW=6 \
BASELINE_LONG_WINDOW=24 \
BASELINE_SHORT_WEIGHT=0.6 \
BASELINE_LONG_WEIGHT=0.4 \
python3 service.py
```

## Notes

- History AI disimpan in-memory selama process `service.py` hidup.
- History analitik memakai time window, default 7 hari terakhir berdasarkan `timestamp`.
- Peak detection butuh minimal 24 sampel komunitas sebelum status selain `warming_up` dianggap valid.
- Untuk production, lebih aman bind AI ke `127.0.0.1` dan expose publik lewat Nginx host.
- Jika backend ada di Docker network yang sama, backend bisa hit `http://nexora-ai:8001`.
- Detail endpoint ada di [API_CONTRACT.md](./API_CONTRACT.md).

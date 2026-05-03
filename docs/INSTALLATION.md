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

Jalankan service dengan Docker Compose:

1. Siapkan file environment:

```bash
cp .env.example .env
```

2. Atur port atau config lain di `.env`

Contoh:

```env
APP_DOMAIN=ai-dev.example.com
APP_PORT=8001
PROXY_PORT=80
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

Penjelasan:

- `APP_DOMAIN`: subdomain/domain yang akan dilayani Nginx
- `APP_PORT`: port internal service AI di docker network
- variable tuning lain dipakai untuk perilaku AI
- container AI sendiri tetap internal-only, tidak expose public port langsung

3. Jalankan service:

```bash
docker compose up -d --build
```

Stop service:

```bash
docker compose down
```

Lihat log:

```bash
docker compose logs -f
```

File compose yang dipakai:

```text
docker-compose.yml
```

File environment contoh:

```text
.env.example
```

## Environment Variables

- `APP_DOMAIN`
- `APP_PORT`
- `PROXY_PORT`
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
APP_DOMAIN=ai-dev.example.com \
PROXY_PORT=80 \
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
- Akses publik dianjurkan lewat Nginx + subdomain, bukan expose port AI service langsung.
- Jika backend ada di `docker-compose` yang sama, backend bisa hit `http://nexora-ai:8001`.
- Detail endpoint ada di [API_CONTRACT.md](./API_CONTRACT.md).

# Nexora AI

Nexora AI adalah engine analitik konsumsi listrik komunitas yang berjalan sebagai service HTTP sederhana. Sistem ini menerima snapshot konsumsi per unit, menyimpan histori in-memory, menghitung baseline komunitas, mendeteksi lonjakan beban, lalu menghasilkan rekomendasi penghematan pada device yang relevan.

## Fitur Utama

- agregasi konsumsi komunitas dari banyak unit
- prediksi baseline komunitas dan unit dari histori aktif
- histori berbasis time window, default 7 hari terakhir
- warm-up minimum sampel sebelum peak detection dianggap siap
- deteksi status komunitas: `warming_up`, `normal`, `high`, `critical`
- rekomendasi device action: `turn_off` atau `reduce`
- fairness counter agar unit yang sama tidak terus-menerus diprioritaskan
- isolasi state per `community_id` agar data antar komunitas tidak bercampur
- HTTP service tanpa dependency eksternal

## Cara Kerja Singkat

1. Client mengirim payload konsumsi ke `POST /analyze` dengan `community_id`.
2. Service membaca histori komunitas dan histori tiap unit dalam window aktif.
3. Service menghitung:
   - prediksi komunitas
   - baseline komunitas
   - trigger `high` dan `critical`
   - baseline tiap unit
4. Service menentukan rekomendasi berdasarkan:
   - deviasi unit dari baseline historisnya
   - kontribusi unit ke beban komunitas saat ini
   - jadwal device
   - fairness memory
5. Response berisi hasil analisis, rekomendasi, dan snapshot state service.

## Status Histori

Project ini sekarang memakai dua mekanisme agar lebih realistis:

- `history window`: default 7 hari terakhir
- `min history samples`: default 24 sampel komunitas

Kalau update datang 1 jam sekali:

- 7 hari window kira-kira berarti 168 sampel maksimum aktif
- 24 sampel warm-up kira-kira berarti 24 jam sebelum peak detection siap penuh

## Menjalankan Service

```bash
python3 service.py
```

Default:

- host: `0.0.0.0`
- port: `8001`

## Docker

```bash
docker build -t nexora-ai .
docker run -d --name nexora-ai -p 8001:8001 nexora-ai
```

## Docker Compose

Project ini sekarang punya dua mode compose:

- `docker-compose.dev.yml` untuk development
- `docker-compose.prod.yml` untuk production/VPS di belakang Nginx host

### Dev

```bash
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

Contoh env dev:

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

Akses dev:

```text
http://127.0.0.1:8001
```

### Prod / VPS

```bash
cp .env.prod.example .env.prod
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Contoh env prod:

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

Mode prod tidak membuka port public langsung. Service dibind ke host lokal VPS, lalu Nginx host melakukan reverse proxy ke sana.

AI service akan tersedia di:

```text
http://127.0.0.1:8001
```

Contoh config Nginx host tersedia di:

```text
nginx/ai.prod.conf.example
```

Setelah subdomain diarahkan lewat Nginx host, akses publiknya menjadi:

```text
http://ai.example.com
```

Kalau backend Anda ada di Docker network yang sama, backend bisa hit AI service lewat:

```text
http://nexora-ai:8001
```

## Dokumentasi

- instalasi: [docs/INSTALLATION.md](./docs/INSTALLATION.md)
- API contract: [docs/API_CONTRACT.md](./docs/API_CONTRACT.md)
- evaluasi: [evaluation/README.md](./evaluation/README.md)

## Struktur File

- [ai_engine.py](/Users/macbook/Workdir/Personal/Projects/nexora/ai/ai_engine.py:1): core engine
- [service.py](/Users/macbook/Workdir/Personal/Projects/nexora/ai/service.py:1): HTTP service
- [requirements.txt](/Users/macbook/Workdir/Personal/Projects/nexora/ai/requirements.txt:1): dependency file
- [docs/INSTALLATION.md](/Users/macbook/Workdir/Personal/Projects/nexora/ai/docs/INSTALLATION.md:1): panduan install dan run
- [docs/API_CONTRACT.md](/Users/macbook/Workdir/Personal/Projects/nexora/ai/docs/API_CONTRACT.md:1): kontrak API

# TikTok Reverse-Engineered REST API

Backend REST API untuk TikTok: Search, Profile, User Videos, Video/Photo Detail, Comments, Trending FYP, dan Direct Media Downloader (video MP4, audio MP3/M4A, foto carousel, cover).

Dibangun dengan **FastAPI** + **Playwright Chromium Pool** yang melewati proteksi Akamai Edge Bot Manager & ByteDance WAF (Slardar/Pumbaa), serta menandatangani setiap request lewat `webmssdk` (`X-Bogus`, `X-Dynosaur`, `msToken`, `ttwid`) secara otomatis di dalam browser.

Dokumentasi lengkap skema request & response ada di **[docs.md](docs.md)**.

---

## 1. Prasyarat Sistem

Linux (Ubuntu / Debian):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip xvfb curl

# Google Chrome (opsional; kalau tidak ada, pakai Chromium bawaan Playwright)
sudo apt install -y google-chrome-stable
```

Kalau Chrome tidak tersedia, pasang Chromium bawaan Playwright:

```bash
.venv/bin/playwright install chromium
.venv/bin/playwright install-deps chromium
```

Backend auto-detect `/usr/bin/google-chrome`, `/usr/bin/google-chrome-stable`, atau `/usr/bin/chromium`. Override manual dengan `CHROME_PATH`.

---

## 2. Instalasi

```bash
cd /root/hehe/tiktok

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

chmod +x run_api.sh
```

---

## 3. Menjalankan Server

### Mode Default (port 8099) — disarankan

Memakai virtual display Xvfb supaya Chromium berjalan **headed**. Halaman SSR (`/api/video/...`, `/api/user/...`) jauh lebih jarang diblokir pada mode ini.

```bash
nohup ./run_api.sh > api_server.log 2>&1 &
```

### Mode Headless Murni (tanpa Xvfb)

Lebih hemat RAM. Endpoint `search`/`trending`/`comments` tetap normal; halaman SSR bisa lebih sering kena blokir Akamai.

```bash
HEADLESS=1 nohup ./run_api.sh > api_server.log 2>&1 &
```

### Environment Variables

| Variable | Default | Fungsi |
|---|---|---|
| `PORT` | `8099` | Port HTTP server |
| `HOST` | `0.0.0.0` | Bind address |
| `HEADLESS` | `0` | `1` = Chromium headless tanpa Xvfb |
| `POOL_SIZE` | `3` | Jumlah page pool paralel untuk in-page API call |
| `CHROME_PATH` | auto-detect | Path binary Chrome/Chromium |

### Operasional

```bash
# Healthcheck
curl -s http://127.0.0.1:8099/health

# Log realtime
tail -f api_server.log

# Stop
pkill -f "uvicorn tiktok_api.app"

# Ganti port
PORT=9000 ./run_api.sh
```

---

## 4. Struktur Project

```
.
├── README.md            # Panduan setup & instalasi
├── docs.md              # Dokumentasi lengkap endpoint + contoh JSON response
├── requirements.txt     # Dependencies Python
├── run_api.sh           # Launcher (Xvfb + Uvicorn)
├── api_server.log       # Log runtime
├── tiktok_api/
│   ├── __init__.py
│   ├── app.py           # FastAPI routes, CORS, media streamer
│   ├── engine.py        # Chromium page pool, warmup, SSR extractor
│   └── service.py       # Business logic: search, user, video, comments, feed
└── .venv/               # Virtual environment
```

---

## 5. Ringkasan Endpoint

Base URL default: `http://127.0.0.1:8099`

| Endpoint | Fungsi |
|---|---|
| `GET /health` | Healthcheck |
| `GET /api/search/videos?q=...` | Cari video berdasarkan keyword |
| `GET /api/search/users?q=...` | Cari akun kreator |
| `GET /api/user/{username}` | Profil lengkap (bio, avatar HD, followers, total likes) |
| `GET /api/user/{username}/videos` | Video yang di-upload user tersebut |
| `GET /api/video/{id_or_url}` | Detail postingan; input boleh ID atau full URL TikTok |
| `GET /api/comments/{video_id}` | Daftar komentar |
| `GET /api/feed/trending` | Video trending / FYP |
| `GET /api/download/post/{id_or_url}` | Katalog link download semua media (video, audio, foto, cover) |
| `GET /api/download/media/{video_id}?target=video\|audio\|cover\|photo&index=0` | Stream file biner langsung dengan header download |

Swagger UI interaktif: `http://<ip-vps>:8099/docs`
ReDoc: `http://<ip-vps>:8099/redoc`

Contoh cepat:

```bash
# Search
curl -s "http://127.0.0.1:8099/api/search/videos?q=kucing&count=5"

# Profil
curl -s "http://127.0.0.1:8099/api/user/khaby.lame"

# Detail video (ID atau URL)
curl -s "http://127.0.0.1:8099/api/video/7700115706221776148"
curl -s "http://127.0.0.1:8099/api/video/https://www.tiktok.com/@cewuul/video/7700115706221776148"

# Download video / audio / foto slide
curl -L -O "http://127.0.0.1:8099/api/download/media/7700115706221776148?target=video"
curl -L -O "http://127.0.0.1:8099/api/download/media/7700115706221776148?target=audio"
curl -L -O "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=photo&index=0"
```

> Setiap URL yang mengandung `&` **wajib** dibungkus tanda kutip di shell, kalau tidak bash akan memotongnya jadi background job.

Payload JSON lengkap untuk semua endpoint: **[docs.md](docs.md)**.

---

## 6. Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| `Target page, context or browser has been closed` saat start | Chromium headed tanpa X server | Jalankan `./run_api.sh` (pakai Xvfb) atau set `HEADLESS=1` |
| `xvfb-run tidak ditemukan` | paket Xvfb belum ada | `sudo apt install -y xvfb` |
| Endpoint search mengembalikan `count: 0` | sesi belum warm / IP diblokir sementara | tunggu 30–60 detik, panggil ulang; cek `api_server.log` |
| Halaman SSR 403 `Access denied` | Akamai menolak navigasi dingin | gunakan mode default (Xvfb/headed), bukan `HEADLESS=1` |
| `curl` mengembalikan `[1] <pid>` | karakter `&` tidak di-quote | bungkus URL dengan `"..."` |
| Download balik 403 | URL CDN diakses langsung tanpa session | pakai endpoint `/api/download/media/...`, jangan URL CDN mentah |

---

## 7. Catatan Teknis

- **Kenapa butuh browser asli?** Endpoint TikTok dan CDN-nya memvalidasi TLS fingerprint + signature `X-Bogus`/`X-Dynosaur` yang dihitung oleh interpreter AST di dalam `webmssdk.js`. Request HTTP mentah dari Python/cURL dijawab `200` dengan body kosong.
- **Page pool**: beberapa tab warm dipakai bergantian supaya request paralel tidak saling merusak execution context.
- **SSR**: tiap pembacaan halaman dibuat di tab baru yang di-warm dulu ke `/explore`, karena navigasi dingin langsung ke URL video ditolak Akamai.
- **Integer overflow**: field `heartCount` dari web JSON TikTok overflow 32-bit (bisa negatif). Backend memakai field `heart` 64-bit yang akurat.
- **Photo mode**: post carousel tidak punya `play_addr`; backend membaca `imagePost.images` dan menyajikan tiap slide resolusi penuh.
- **Audio**: CDN sering melabeli audio M4A sebagai `video/mp4`. Backend menyaring magic byte sehingga `Content-Type` dan ekstensi file selalu benar (`audio/mpeg` `.mp3` atau `audio/mp4` `.m4a`).

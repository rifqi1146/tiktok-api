# TikTok Reverse-Engineered REST API — Dokumentasi Lengkap

Dokumentasi resmi untuk backend service TikTok REST API yang di-reverse engineer dari TikTok APK v47.6.2 dan web platform.

Service ini berjalan di background port **`8099`** (`http://127.0.0.1:8099` atau `http://0.0.0.0:8099`) menggunakan engine Chromium ter-otentikasi (Playwright + Xvfb) yang mem-bypass seluruh proteksi Akamai Edge, Cloudflare, ByteDance WAF (Slardar/Pumbaa), serta menandatangani request dengan `webmssdk` (`X-Bogus`, `X-Dynosaur`, `msToken`, `ttwid`).

---

## 1. Quick Start & Service Control

Service sudah berjalan dan siap dipanggil oleh frontend:

```bash
# Cek service status
curl -s http://127.0.0.1:8099/health

# Buka Swagger UI interaktif di browser
http://<ip-server>:8099/docs

# Restart service manual jika diperlukan
pkill -f "uvicorn tiktok_api.app"
cd /root/hehe/tiktok && nohup /usr/bin/xvfb-run -a -s "-screen 0 1440x900x24" /root/hehe/tiktok/.venv/bin/uvicorn tiktok_api.app:app --host 0.0.0.0 --port 8099 > /root/hehe/tiktok/api_server.log 2>&1 &
```

---

## 2. Ringkasan Endpoint

| Method | Endpoint | Fungsi |
|---|---|---|
| `GET` | `/health` | Healthcheck status server |
| `GET` | `/api/search/videos?q=...` | Cari video berdasarkan kata kunci |
| `GET` | `/api/search/users?q=...` | Cari akun/kreator berdasarkan nama/kata kunci |
| `GET` | `/api/user/{username}` | Detail profil lengkap kreator |
| `GET` | `/api/user/{username}/videos` | Daftar video yang di-upload oleh user |
| `GET` | `/api/video/{video_id_or_url}` | Detail lengkap video/foto (mendukung ID atau Full URL) |
| `GET` | `/api/comments/{video_id}` | Daftar komentar pada suatu postingan |
| `GET` | `/api/feed/trending` | Feed video rekomendasi / FYP terkini |
| `GET` | `/api/download/post/{video_id_or_url}` | **Info Downloader Terpadu**: URL download direct & proxy untuk semua aset (video, audio, foto-foto, cover) |
| `GET` | `/api/download/media/{video_id}` | **Direct Media Streamer**: download biner langsung (`target=video\|audio\|cover\|photo`) |
| `GET` | `/api/download?url=...` | Generic CDN proxy streamer dengan range header forwarding |

---

## 3. Detail Request & Response Setiap Endpoint

### 3.1. Search Videos
Mencari video di TikTok berdasarkan query.

* **Method:** `GET`
* **Path:** `/api/search/videos`
* **Query Parameters:**
  * `q` (string, required): Kata kunci pencarian (misal: `kucing`, `meme`, `resep masakan`)
  * `count` (integer, optional, default: `15`, max: `50`): Jumlah video per request
  * `offset` (integer, optional, default: `0`): Offset untuk paginasi
  * `region` (string, optional, default: `ID`): Kode negara (`ID`, `US`, `SG`, dll)

#### Contoh Request:
```bash
curl -s "http://127.0.0.1:8099/api/search/videos?q=kucing&count=2"
```

#### Contoh Response:
```json
{
  "status_code": 0,
  "keyword": "kucing",
  "count": 2,
  "cursor": 2,
  "has_more": true,
  "videos": [
    {
      "id": "7175743869638708507",
      "desc": "Saya mendengar bunyi ini blh menarik perhatian kucing😆cepat cuba🧐#cat #catmeow #meow #kucing #bunyi #kucingtiktok #kucingmeow #fyp ",
      "type": "video",
      "create_time": 1670733069,
      "author": {
        "id": "7143147413678212122",
        "unique_id": "pets_llover",
        "nickname": "Household Pets Viral",
        "avatar": "https://p16-common-sign.tiktokcdn.com/...jpg",
        "verified": false,
        "sec_uid": "MS4wLjABAAAA5n7rCwWN...",
        "signature": "Funny and cute pets videos every day."
      },
      "stats": {
        "play_count": 27400000,
        "digg_count": 330400,
        "comment_count": 22400,
        "share_count": 24200,
        "collect_count": 78600
      },
      "video": {
        "duration": 14,
        "ratio": "540p",
        "width": 576,
        "height": 1024,
        "cover": "https://p16-common-sign.tiktokcdn.com/...jpg",
        "dynamic_cover": "https://p16-common-sign.tiktokcdn.com/...webp",
        "origin_cover": "https://p16-common-sign.tiktokcdn.com/...jpg",
        "play_addr": "https://v16-webapp-prime.tiktok.com/video/tos/alisg/...mp4",
        "download_addr": "https://v16-webapp-prime.tiktok.com/video/tos/alisg/...mp4",
        "format": "mp4",
        "bitrate": 1048576
      },
      "images": [],
      "music": {
        "id": "7175743890887101211",
        "title": "original sound - Household Pets Viral",
        "author": "Household Pets Viral",
        "duration": 14,
        "play_url": "https://sf16-ies-music-sg.tiktokcdn.com/...mp3",
        "cover": "https://p16-common-sign.tiktokcdn.com/...jpg",
        "original": true
      },
      "share_url": "https://www.tiktok.com/@pets_llover/video/7175743869638708507"
    }
  ]
}
```

---

### 3.2. Search Users
Mencari profil kreator / akun pengguna.

* **Method:** `GET`
* **Path:** `/api/search/users`
* **Query Parameters:**
  * `q` (string, required): Nama akun atau display name yang dicari
  * `count` (integer, optional, default: `10`)
  * `region` (string, optional, default: `ID`)

#### Contoh Request:
```bash
curl -s "http://127.0.0.1:8099/api/search/users?q=khaby&count=1"
```

#### Contoh Response:
```json
{
  "status_code": 0,
  "keyword": "khaby",
  "count": 1,
  "users": [
    {
      "uid": "127905465618821121",
      "unique_id": "khaby.lame",
      "nickname": "Khabane lame",
      "avatar": {
        "uri": "tos-maliva-avt-0068/08987e23b94057953fd4f1738694bf5f",
        "url_list": [
          "https://p16-common-sign.tiktokcdn.com/...webp"
        ],
        "width": 720,
        "height": 720
      },
      "signature": "Se vuoi ridere sei nel posto giusto😎 If u wanna laugh u r in the right place😎",
      "verified": true,
      "follower_count": 163000000,
      "total_favorited": 2691797734,
      "sec_uid": "MS4wLjABAAAAwAg0rSzO65WQfz4RzQgGv2Xdv108BgPXhRrrmNVIHQZ9PO8-flwwRtEppYTS0OjA",
      "profile_url": "https://www.tiktok.com/@khaby.lame"
    }
  ]
}
```

---

### 3.3. User Profile
Mengambil detail metadata profil lengkap termasuk angka followers, following, likes, bio, link bio, foto avatar resolusi tinggi, dan badge verified.

* **Method:** `GET`
* **Path:** `/api/user/{username}` (bisa dengan `@` atau tanpa `@`)

#### Contoh Request:
```bash
curl -s "http://127.0.0.1:8099/api/user/khaby.lame"
```

#### Contoh Response:
```json
{
  "status": "ok",
  "user": {
    "id": "127905465618821121",
    "unique_id": "khaby.lame",
    "nickname": "Khabane lame",
    "avatar_larger": "https://p16-common-sign.tiktokcdn.com/tos-maliva-avt-0068/...jpeg",
    "avatar_medium": "https://p16-common-sign.tiktokcdn.com/tos-maliva-avt-0068/...jpeg",
    "avatar_thumb": "https://p16-common-sign.tiktokcdn.com/tos-maliva-avt-0068/...jpeg",
    "signature": "Se vuoi ridere sei nel posto giusto😎 If u wanna laugh u r in the right place😎",
    "verified": true,
    "sec_uid": "MS4wLjABAAAAwAg0rSzO65WQfz4RzQgGv2Xdv108BgPXhRrrmNVIHQZ9PO8-flwwRtEppYTS0OjA",
    "private_account": false,
    "relation": 0,
    "bio_link": null,
    "profile_url": "https://www.tiktok.com/@khaby.lame"
  },
  "stats": {
    "follower_count": 163000000,
    "following_count": 82,
    "heart_count": 2700000000,
    "video_count": 1359,
    "digg_count": 0,
    "friend_count": 77
  },
  "share_meta": {
    "title": "Khabane lame (@khaby.lame) on TikTok",
    "desc": "Khabane lame (@khaby.lame) on TikTok | 2.7B Likes. 163M Followers. Se vuoi ridere sei nel posto giusto😎 If u wanna laugh u r in the right place😎"
  }
}
```

---

### 3.4. User Videos
Mengambil daftar video terbaru/terpopuler yang diunggah oleh kreator spesifik.

* **Method:** `GET`
* **Path:** `/api/user/{username}/videos`
* **Query Parameters:**
  * `count` (integer, optional, default: `20`, max: `50`)
  * `region` (string, optional, default: `ID`)

#### Contoh Request:
```bash
curl -s "http://127.0.0.1:8099/api/user/khaby.lame/videos?count=2"
```

#### Contoh Response:
```json
{
  "status": "ok",
  "username": "khaby.lame",
  "count": 2,
  "exact_matches": 8,
  "videos": [
    {
      "id": "7646812028874673439",
      "desc": "Thank you, please come again!!!🙋🏿‍♂️💸#learnfromkhaby #comedy ",
      "type": "video",
      "create_time": 1780412195,
      "author": {
        "id": "127905465618821121",
        "unique_id": "khaby.lame",
        "nickname": "Khabane lame",
        "avatar": "https://p16-common-sign.tiktokcdn.com/...jpeg",
        "verified": true,
        "sec_uid": "MS4wLjABAAAAwAg0rSzO...",
        "signature": "Se vuoi ridere sei nel posto giusto😎"
      },
      "stats": {
        "play_count": 19900000,
        "digg_count": 1900000,
        "comment_count": 19400,
        "share_count": 19800,
        "collect_count": 78100
      },
      "video": {
        "duration": 29,
        "ratio": "720p",
        "width": 720,
        "height": 1280,
        "cover": "https://p16-common-sign.tiktokcdn.com/...jpeg",
        "dynamic_cover": "https://p16-common-sign.tiktokcdn.com/...webp",
        "play_addr": "https://v16-webapp-prime.tiktok.com/...mp4",
        "format": "mp4"
      },
      "music": {
        "id": "7646812056230349600",
        "title": "original sound - Khabane lame",
        "author": "Khabane lame",
        "duration": 29,
        "play_url": "https://sf16-ies-music-sg.tiktokcdn.com/...mp3"
      },
      "share_url": "https://www.tiktok.com/@khaby.lame/video/7646812028874673439"
    }
  ]
}
```

---

### 3.5. Video Detail (Bisa Menerima ID atau URL TikTok Langsung)
Mengambil detail satu postingan TikTok. Mendukung **Video biasa** dan **Postingan Foto / Slide / Carousel**.

* **Method:** `GET`
* **Path:** `/api/video/{video_id_or_url}`
* **Input yang didukung:**
  * Numeric ID saja: `/api/video/7700115706221776148`
  * Full URL web: `/api/video/https://www.tiktok.com/@cewuul/video/7700115706221776148`
  * URL dengan query param: `curl -s "http://127.0.0.1:8099/api/video/https://www.tiktok.com/@cewuul/video/7700115706221776148?is_from_webapp=1&sender_device=pc"`

#### Contoh Response Video Post:
```json
{
  "id": "7700115706221776148",
  "desc": "OOTD santai",
  "type": "video",
  "create_time": "1792822901",
  "author": {
    "id": "7441084520495940664",
    "unique_id": "cewuul",
    "nickname": "cewuul",
    "avatar": "https://p16-common-sign.tiktokcdn.com/...jpeg",
    "verified": false,
    "sec_uid": "MS4wLjABAAAAzovvFqBT60D1jpfJxgAkz5wDVbpkP_QeNzjliuPV7ooRWjly9IkCkGORfaW8Oa4t",
    "signature": "akun kedua @wuulan"
  },
  "stats": {
    "play_count": 65100,
    "digg_count": 9975,
    "comment_count": 41,
    "share_count": 1094,
    "collect_count": "759"
  },
  "video": {
    "duration": 26,
    "ratio": "540p",
    "width": 576,
    "height": 1024,
    "cover": "https://p16-common-sign.tiktokcdn.com/...image",
    "dynamic_cover": "https://p19-common-sign.tiktokcdn.com/...image",
    "origin_cover": "https://p16-common-sign.tiktokcdn.com/...image",
    "play_addr": "https://v16-webapp-prime.tiktok.com/video/tos/alisg/...mp4",
    "download_addr": "",
    "format": null,
    "bitrate": null
  },
  "images": [],
  "music": {
    "id": "7700115730389306144",
    "title": "Adambarai",
    "author": "DJ Amo",
    "duration": 60,
    "play_url": "https://sf16-ies-music-sg.tiktokcdn.com/...mp3",
    "cover": "https://p16-common-sign.tiktokcdn.com/...jpeg",
    "original": false
  },
  "share_url": "https://www.tiktok.com/@cewuul/video/7700115706221776148",
  "status": "ok"
}
```

#### Contoh Response Photo / Carousel Post (`type: "photo"`):
```json
{
  "id": "7693493910332509448",
  "desc": "resep kue",
  "type": "photo",
  "create_time": "1791281145",
  "author": {
    "id": "7625977327206728712",
    "unique_id": "amirabat2_",
    "nickname": "mira",
    "avatar": "https://p16-common-sign.tiktokcdn.com/...jpeg"
  },
  "stats": {
    "play_count": 96700,
    "digg_count": 6236,
    "comment_count": 1,
    "share_count": 2142,
    "collect_count": "1778"
  },
  "video": {
    "duration": 0,
    "ratio": "",
    "width": 0,
    "height": 0,
    "cover": "https://p16-common-sign.tiktokcdn.com/tos-alisg-i-photomode-sg/...jpeg",
    "play_addr": ""
  },
  "images": [
    {
      "url": "https://p16-common-sign.tiktokcdn.com/tos-alisg-i-photomode-sg/2bac80eadcaf4b62b0b82e329128244c~tplv-photomode-image.jpeg?...",
      "url_list": [
        "https://p16-common-sign.tiktokcdn.com/...",
        "https://p19-common-sign.tiktokcdn.com/..."
      ],
      "width": 1228,
      "height": 2180
    },
    {
      "url": "https://p16-common-sign.tiktokcdn.com/tos-alisg-i-photomode-sg/1f31f90ac83f4b889345e69e06c5ee00~tplv-photomode-image.jpeg?...",
      "url_list": [
        "https://p16-common-sign.tiktokcdn.com/..."
      ],
      "width": 1228,
      "height": 2180
    }
  ],
  "music": {
    "id": "7536233538052508422",
    "title": "suara asli - Avp Music Player🎧",
    "author": "Avp Music Player🎧",
    "duration": 232,
    "play_url": "https://v45.tiktokcdn.com/...mp3"
  },
  "status": "ok"
}
```

---

### 3.6. Video Comments
Mengambil daftar komentar publik dari sebuah video.

* **Method:** `GET`
* **Path:** `/api/comments/{video_id}`
* **Query Parameters:**
  * `count` (integer, optional, default: `20`, max: `50`)
  * `cursor` (integer, optional, default: `0`)
  * `region` (string, optional, default: `ID`)

#### Contoh Request:
```bash
curl -s "http://127.0.0.1:8099/api/comments/7700570105230478598?count=2"
```

#### Contoh Response:
```json
{
  "status_code": 0,
  "video_id": "7700570105230478598",
  "total": 417,
  "count": 2,
  "cursor": 2,
  "has_more": true,
  "comments": [
    {
      "cid": "7700571234567890123",
      "text": "How did this mf get ahold of a bus bro",
      "create_time": 1792929421,
      "digg_count": 5736,
      "reply_total": 42,
      "author": {
        "uid": "6812345678901234567",
        "unique_id": "dominionerofthepinzhao",
        "nickname": "Pinzhao",
        "avatar": "https://p16-common-sign.tiktokcdn.com/...jpeg"
      }
    }
  ]
}
```

---

### 3.7. Trending Feed
Mengambil video rekomendasi FYP / Trending terkini.

* **Method:** `GET`
* **Path:** `/api/feed/trending`
* **Query Parameters:**
  * `count` (integer, optional, default: `15`, max: `50`)
  * `region` (string, optional, default: `ID`)

#### Contoh Request:
```bash
curl -s "http://127.0.0.1:8099/api/feed/trending?count=2"
```

---

## 4. API Downloader (Support Semua Tipe: Video, Audio, Foto, Cover)

TikTok memproteksi CDN-nya menggunakan referer check dan session cookies. Jika user biasa mengakses direct URL TikTok CDN dari browser luar tanpa header yang sesuai, TikTok mengembalikan `403 Forbidden`.

Oleh karena itu backend menyediakan **2 skema downloader**:

### Skema A — Info Downloader Terpadu (`/api/download/post/{id}`)
Frontend memanggil endpoint ini untuk mendapatkan katalog link download yang siap disajikan ke UI:

* **Method:** `GET`
* **Path:** `/api/download/post/{video_id_or_url}`

#### Contoh Request:
```bash
curl -s "http://127.0.0.1:8099/api/download/post/7700115706221776148"
```

#### Contoh Response untuk Video Post:
```json
{
  "id": "7700115706221776148",
  "type": "video",
  "desc": "OOTD santai",
  "author": "cewuul",
  "media": {
    "audio": {
      "title": "Adambarai",
      "author": "DJ Amo",
      "duration": 60,
      "direct_url": "https://sf16-ies-music-sg.tiktokcdn.com/...mp3",
      "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7700115706221776148?target=audio"
    },
    "video": {
      "duration": 26,
      "width": 576,
      "height": 1024,
      "direct_url": "https://v16-webapp-prime.tiktok.com/...mp4",
      "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7700115706221776148?target=video"
    },
    "cover": {
      "direct_url": "https://p16-common-sign.tiktokcdn.com/...image",
      "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7700115706221776148?target=cover"
    }
  }
}
```

#### Contoh Response untuk Photo Post:
```json
{
  "id": "7693493910332509448",
  "type": "photo",
  "desc": "resep kue",
  "author": "amirabat2_",
  "media": {
    "audio": {
      "title": "suara asli - Avp Music Player🎧",
      "author": "Avp Music Player🎧",
      "duration": 232,
      "direct_url": "https://v45.tiktokcdn.com/...mp3",
      "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=audio"
    },
    "photos": [
      {
        "index": 0,
        "width": 1228,
        "height": 2180,
        "direct_url": "https://p16-common-sign.tiktokcdn.com/...jpeg",
        "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=photo&index=0"
      },
      {
        "index": 1,
        "width": 1228,
        "height": 2180,
        "direct_url": "https://p16-common-sign.tiktokcdn.com/...jpeg",
        "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=photo&index=1"
      },
      {
        "index": 2,
        "width": 1228,
        "height": 2180,
        "direct_url": "https://p16-common-sign.tiktokcdn.com/...jpeg",
        "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=photo&index=2"
      }
    ],
    "cover": {
      "direct_url": "https://p16-common-sign.tiktokcdn.com/...jpeg",
      "proxy_download_url": "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=cover"
    }
  }
}
```

---

### Skema B — Direct Media Streamer (`/api/download/media/{id}`)
Endpoint ini langsung mengalirkan file biner ke client dengan header `Content-Disposition: attachment; filename="tiktok_...mp4"` sehingga browser user otomatis men-download file dengan ekstensi dan MIME type yang tepat.

* **Method:** `GET`
* **Path:** `/api/download/media/{video_id}`
* **Query Parameters:**
  * `target`: Media yang mau di-download:
    * `video` -> download file MP4 video (`video/mp4`)
    * `audio` -> download audio suara asli / musik. Backend menyaring magic bytes: file MP3 asli dikirim sebagai `audio/mpeg` (`.mp3`), sedangkan audio M4A dikirim sebagai `audio/mp4` (`.m4a`). TikTok CDN sendiri sering salah melabeli audio M4A sebagai `video/mp4`, jadi tipe file di-sniff dari header biner, bukan dari URL.
    * `photo` -> download salah satu foto slide (`image/jpeg`)
    * `cover` -> download gambar cover (`image/jpeg`)
  * `index` (integer, optional, default: `0`): Urutan foto (hanya untuk `target=photo`)

#### Contoh Download Video MP4:
```bash
curl -L -O "http://127.0.0.1:8099/api/download/media/7700115706221776148?target=video"
# File tersimpan sebagai: tiktok_7700115706221776148.mp4
```

#### Contoh Download Audio (MP3 atau M4A otomatis):
```bash
curl -L -O "http://127.0.0.1:8099/api/download/media/7700115706221776148?target=audio"
# File tersimpan sebagai: tiktok_7700115706221776148_audio.m4a  (jika sumbernya M4A)
# atau:                   tiktok_7700115706221776148_audio.mp3  (jika sumbernya MP3)
```

#### Contoh Download Foto Slide 1 dan 2:
```bash
curl -L -O "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=photo&index=0"
# File tersimpan sebagai: tiktok_7693493910332509448_photo_1.jpeg

curl -L -O "http://127.0.0.1:8099/api/download/media/7693493910332509448?target=photo&index=1"
# File tersimpan sebagai: tiktok_7693493910332509448_photo_2.jpeg
```

---

## 5. Contoh Integrasi Frontend (JavaScript / React / Vue / Axios)

### 5.1. Fetch Search Videos
```javascript
const API_BASE = "http://127.0.0.1:8099";

async function searchTikTokVideos(keyword, count = 15, offset = 0) {
  const res = await fetch(`${API_BASE}/api/search/videos?q=${encodeURIComponent(keyword)}&count=${count}&offset=${offset}`);
  const data = await res.json();
  console.log(`Ditemukan ${data.count} video:`, data.videos);
  return data.videos;
}
```

### 5.2. Fetch User Profile & User Videos
```javascript
async function getUserProfileAndVideos(username) {
  // 1. Ambil info profil
  const profileRes = await fetch(`${API_BASE}/api/user/${username}`);
  const profile = await profileRes.json();
  console.log("Followers:", profile.stats.follower_count);

  // 2. Ambil daftar video user
  const videosRes = await fetch(`${API_BASE}/api/user/${username}/videos?count=20`);
  const videos = await videosRes.json();
  console.log("Videos:", videos.videos);

  return { profile: profile.user, stats: profile.stats, videos: videos.videos };
}
```

### 5.3. Komponen Downloader TikTok Lengkap (React / Vanilla JS)
```javascript
async function handleDownloadTikTok(inputUrlOrId) {
  // Panggil endpoint downloader info
  const encoded = encodeURIComponent(inputUrlOrId);
  const res = await fetch(`${API_BASE}/api/download/post/${encoded}`);
  if (!res.ok) {
    throw new Error("Video tidak ditemukan atau link salah.");
  }
  const post = await res.json();

  if (post.type === "video") {
    // Siapkan tombol Download Video & Audio
    console.log("Link Download MP4:", post.media.video.proxy_download_url);
    console.log("Link Download MP3:", post.media.audio.proxy_download_url);

    // Untuk trigger download langsung di browser user:
    window.location.href = post.media.video.proxy_download_url;
  } else if (post.type === "photo") {
    // Siapkan list foto untuk di-download satu per satu
    console.log(`Postingan ini memiliki ${post.media.photos.length} foto`);
    post.media.photos.forEach((photo) => {
      console.log(`Foto Slide ${photo.index + 1}:`, photo.proxy_download_url);
    });
    // Download audio latar
    console.log("Audio Musik:", post.media.audio.proxy_download_url);
  }
}
```

---

## 6. Penanganan Error (Status Codes)

* `200 OK`: Request sukses.
* `400 Bad Request`: Input tidak valid (misal: index foto melebihi jumlah foto yang ada, CDN domain ilegal).
* `404 Not Found`: Akun TikTok tidak ditemukan, video sudah dihapus, atau video di-set private oleh pemiliknya.
* `500 Internal Server Error`: TikTok WAF challenge sementara atau network timeout ke TikTok edge.

Format response error:
```json
{
  "detail": "Video '1000000000000000000' not found, deleted, or restricted."
}
```

---

## 7. Arsitektur Internal & Catatan Teknis Reversing

1. **Kenapa butuh Browser Context Pool (`TikTokBrowserEngine`)?**
   * Endpoint TikTok `/api/search/...`, `/api/recommend/...`, dan CDN streaming dilindungi oleh Akamai Edge Bot Management & ByteDance Slardar WAF.
   * `webmssdk.js` secara otomatis mem-patch `window.fetch` untuk menghitung hash signature query `X-Dynosaur` dan `X-Bogus` menggunakan AST interpreter di dalam browser, serta mengirim header cookie `ttwid` dan `msToken`.
   * Permintaan HTTP mentah dari Python/cURL tanpa session TLS Chrome asli akan menghasilkan empty 200 (0 bytes) atau HTTP 403 Forbidden.
   * Engine internal kita memelihara 3 page pool yang siap menjalankan in-page signed fetch secara real-time dan paralel tanpa re-login.

2. **Resolusi 64-bit Integer pada Like Count:**
   * Di respons web JSON TikTok terdapat bug integer overflow 32-bit pada field `heartCount` (misal nilai negatif `-1,603,173,633`).
   * Backend ini secara otomatis mendeteksi dan mengambil field `heart` 64-bit asli (`2,700,000,000` / 2.7 Miliar Likes) sehingga data akurat.

3. **Multi-Media Photo Posts:**
   * TikTok Carousel / Photo Mode tidak memiliki `play_addr` video.
   * Backend mendeteksi struktur `imagePost` dan mengekstrak array `images` lengkap dengan resolusi asli dan multiple CDN mirror fallback.

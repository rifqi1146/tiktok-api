import asyncio
import logging
import re
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from tiktok_api.engine import engine
from tiktok_api.service import service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tiktok.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await engine.start()
    yield
    await engine.stop()


app = FastAPI(
    title="TikTok Reverse-Engineered REST API",
    description="Full-featured TikTok extraction & downloader API (Search, Profiles, Videos, Photos, Audio, Comments, Trending).",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "TikTok REST API (Reverse Engineered)",
        "version": "1.1.0",
        "endpoints": {
            "health": "GET /health",
            "search_videos": "GET /api/search/videos?q=<keyword>&count=15&offset=0&region=ID",
            "search_users": "GET /api/search/users?q=<keyword>&count=10&region=ID",
            "user_profile": "GET /api/user/{username}",
            "user_videos": "GET /api/user/{username}/videos?count=20&region=ID",
            "video_detail": "GET /api/video/{video_id_or_url}",
            "video_comments": "GET /api/comments/{video_id}?count=20&cursor=0&region=ID",
            "trending_feed": "GET /api/feed/trending?count=15&region=ID",
            "downloader_info": "GET /api/download/post/{video_id_or_url}",
            "downloader_stream": "GET /api/download/media/{video_id}?target=video|audio|cover|photo&index=0",
            "raw_proxy": "GET /api/download?url=<cdn_url>&filename=tiktok.mp4",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------- Search
@app.get("/api/search/videos")
async def search_videos(
    q: str = Query(..., description="Search keyword"),
    count: int = Query(15, ge=1, le=50),
    offset: int = Query(0, ge=0),
    region: str = Query("ID"),
):
    try:
        return await service.search_videos(q, count=count, offset=offset, region=region)
    except Exception as e:
        logger.exception("search_videos failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/users")
async def search_users(
    q: str = Query(..., description="Username or keyword"),
    count: int = Query(10, ge=1, le=30),
    offset: int = Query(0, ge=0),
    region: str = Query("ID"),
):
    try:
        return await service.search_users(q, count=count, offset=offset, region=region)
    except Exception as e:
        logger.exception("search_users failed")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------------ User
@app.get("/api/user/{username}")
async def get_user(username: str):
    try:
        res = await service.get_user_profile(username)
        if res.get("status") == "error":
            raise HTTPException(status_code=404, detail=res["message"])
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_user failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user/{username}/videos")
async def get_user_videos(
    username: str,
    count: int = Query(20, ge=1, le=50),
    region: str = Query("ID"),
):
    try:
        return await service.get_user_videos(username, count=count, region=region)
    except Exception as e:
        logger.exception("get_user_videos failed")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------------- Video
@app.get("/api/video/{video_id_or_url:path}")
async def get_video(video_id_or_url: str):
    try:
        res = await service.get_video_detail(video_id_or_url)
        if res.get("status") == "error":
            raise HTTPException(status_code=404, detail=res["message"])
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_video failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/comments/{video_id}")
async def get_comments(
    video_id: str,
    count: int = Query(20, ge=1, le=50),
    cursor: int = Query(0, ge=0),
    region: str = Query("ID"),
):
    try:
        return await service.get_video_comments(video_id, count=count, cursor=cursor, region=region)
    except Exception as e:
        logger.exception("get_comments failed")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------------ Feed
@app.get("/api/feed/trending")
async def get_trending(
    count: int = Query(15, ge=1, le=50),
    region: str = Query("ID"),
):
    try:
        return await service.get_trending_feed(count=count, region=region)
    except Exception as e:
        logger.exception("get_trending failed")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------ Downloader
@app.get("/api/download/post/{video_id_or_url:path}")
async def download_post_info(video_id_or_url: str, request: Request):
    """
    Returns structured download URLs for all media types of any post:
    - video MP4 (with and without watermark playAddr)
    - photos (high-res image URLs for all slides if photo post)
    - audio MP3 / original sound
    - animated / static covers
    """
    res = await service.get_video_detail(video_id_or_url)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail=res["message"])

    vid = res.get("id")
    base_url = str(request.base_url).rstrip("/")
    post_type = res.get("type", "video")

    downloads = {
        "id": vid,
        "type": post_type,
        "desc": res.get("desc"),
        "author": res.get("author", {}).get("unique_id"),
        "media": {},
    }

    # Audio
    music = res.get("music") or {}
    if music.get("play_url"):
        downloads["media"]["audio"] = {
            "title": music.get("title"),
            "author": music.get("author"),
            "duration": music.get("duration"),
            "direct_url": music.get("play_url"),
            "proxy_download_url": f"{base_url}/api/download/media/{vid}?target=audio",
        }

    # Video or Photos
    if post_type == "video":
        play_addr = res.get("video", {}).get("play_addr")
        if play_addr:
            downloads["media"]["video"] = {
                "duration": res.get("video", {}).get("duration"),
                "width": res.get("video", {}).get("width"),
                "height": res.get("video", {}).get("height"),
                "direct_url": play_addr,
                "proxy_download_url": f"{base_url}/api/download/media/{vid}?target=video",
            }
    elif post_type == "photo":
        photos = []
        for idx, img in enumerate(res.get("images", [])):
            photos.append({
                "index": idx,
                "width": img.get("width"),
                "height": img.get("height"),
                "direct_url": img.get("url"),
                "proxy_download_url": f"{base_url}/api/download/media/{vid}?target=photo&index={idx}",
            })
        downloads["media"]["photos"] = photos

    # Covers
    cov = res.get("video", {}).get("cover")
    if cov:
        downloads["media"]["cover"] = {
            "direct_url": cov,
            "proxy_download_url": f"{base_url}/api/download/media/{vid}?target=cover",
        }

    return downloads


@app.get("/api/download/media/{video_id}")
async def download_media(
    video_id: str,
    target: str = Query("video", pattern="^(video|audio|cover|photo)$"),
    index: int = Query(0, ge=0),
    request: Request = None,
):
    """
    Streams one media asset of a post with a correct Content-Type and download filename.

    target: video (mp4) | audio (mp3/m4a) | cover (jpeg) | photo (jpeg slide)
    index:  photo slide index, only for target=photo
    """
    res = await service.get_video_detail(video_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail=res["message"])

    if target == "video":
        url = res.get("video", {}).get("play_addr")
        filename, media_type = f"tiktok_{video_id}.mp4", "video/mp4"
    elif target == "audio":
        url = (res.get("music") or {}).get("play_url")
        # TikTok serves original sounds as either ID3-tagged MP3 or M4A, and the
        # CDN often labels both "video/mp4"; pick the container from the URL.
        if url and ".m4a" in url.lower():
            filename, media_type = f"tiktok_{video_id}_audio.m4a", "audio/mp4"
        else:
            filename, media_type = f"tiktok_{video_id}_audio.mp3", "audio/mpeg"
    elif target == "cover":
        url = res.get("video", {}).get("cover")
        filename, media_type = f"tiktok_{video_id}_cover.jpeg", "image/jpeg"
    else:  # photo
        images = res.get("images", [])
        if not images:
            raise HTTPException(status_code=404, detail="This post contains no photo slides.")
        if index >= len(images):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid photo index {index}; total is {len(images)}.",
            )
        url = images[index].get("url")
        filename, media_type = f"tiktok_{video_id}_photo_{index + 1}.jpeg", "image/jpeg"

    if not url:
        raise HTTPException(
            status_code=404,
            detail=f"Target '{target}' media not available for post {video_id}.",
        )

    range_hdr = request.headers.get("range") if request else None
    resp, client = await service.proxy_video_stream(url, range_header=range_hdr)

    # Peek first chunk so magic bytes dictate the exact MIME type & extension
    aiter = resp.aiter_bytes(65536)
    try:
        first_chunk = await anext(aiter)
    except (StopAsyncIteration, Exception):
        first_chunk = b""

    if target == "audio":
        if b"ftypM4A" in first_chunk[:32] or b"ftypmp42" in first_chunk[:32]:
            media_type = "audio/mp4"
            filename = f"tiktok_{video_id}_audio.m4a"
        else:
            media_type = "audio/mpeg"
            filename = f"tiktok_{video_id}_audio.mp3"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": media_type,
    }
    for k in ("content-length", "content-range", "accept-ranges"):
        if k in resp.headers:
            headers[k] = resp.headers[k]

    async def streamer():
        try:
            if first_chunk:
                yield first_chunk
            async for chunk in aiter:
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        streamer(),
        status_code=resp.status_code,
        headers=headers,
        media_type=media_type,
    )


@app.get("/api/download")
async def download_raw_url(
    url: str = Query(..., description="Direct TikTok CDN URL"),
    filename: Optional[str] = Query(None),
    request: Request = None,
):
    """Generic raw CDN proxy with Range header forwarding."""
    if not any(d in url for d in ("tiktok", "tiktokcdn", "akamaized", "byteoversea", "ibytedtos")):
        raise HTTPException(status_code=400, detail="Invalid CDN URL domain.")
    try:
        range_hdr = request.headers.get("range") if request else None
        resp, client = await service.proxy_video_stream(url, range_header=range_hdr)

        async def streamer():
            try:
                async for chunk in resp.aiter_bytes(65536):
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        headers = {}
        for k in ("content-length", "content-range", "accept-ranges"):
            if k in resp.headers:
                headers[k] = resp.headers[k]

        ct = resp.headers.get("content-type", "application/octet-stream")
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        return StreamingResponse(
            streamer(),
            status_code=resp.status_code,
            headers=headers,
            media_type=ct,
        )
    except Exception as e:
        logger.exception("download raw failed")
        raise HTTPException(status_code=500, detail=str(e))

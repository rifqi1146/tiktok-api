import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from tiktok_api.engine import engine

logger = logging.getLogger("tiktok.service")

JS_FETCH_JSON = """async (url) => {
    try {
        const res = await fetch(url, {credentials: 'include'});
        const txt = await res.text();
        if (!txt) return {status: res.status, ok: false, empty: true, json: null};
        try {
            return {status: res.status, ok: true, json: JSON.parse(txt)};
        } catch (e) {
            return {status: res.status, ok: false, error: 'json_parse', raw: txt.slice(0, 200)};
        }
    } catch (e) {
        return {status: 0, ok: false, error: String(e)};
    }
}"""


class TikTokService:
    @staticmethod
    def _clean_video_item(it: Dict[str, Any]) -> Dict[str, Any]:
        if not it:
            return {}
        video = it.get("video") or {}
        author = it.get("author") or {}
        stats = it.get("stats") or {}
        music = it.get("music") or {}

        images = []
        image_post = it.get("imagePost") or {}
        for img in image_post.get("images", []):
            url_list = (img.get("imageURL") or {}).get("urlList") or []
            if url_list:
                images.append({
                    "url": url_list[0],
                    "url_list": url_list,
                    "width": img.get("imageWidth"),
                    "height": img.get("imageHeight"),
                })

        is_photo = bool(images) or not video.get("playAddr")

        return {
            "id": it.get("id"),
            "desc": it.get("desc") or "",
            "type": "photo" if is_photo else "video",
            "create_time": it.get("createTime"),
            "author": {
                "id": author.get("id"),
                "unique_id": author.get("uniqueId"),
                "nickname": author.get("nickname"),
                "avatar": author.get("avatarThumb") or author.get("avatarMedium"),
                "verified": author.get("verified", False),
                "sec_uid": author.get("secUid"),
                "signature": author.get("signature", ""),
            },
            "stats": {
                "play_count": stats.get("playCount", 0),
                "digg_count": stats.get("diggCount", 0),
                "comment_count": stats.get("commentCount", 0),
                "share_count": stats.get("shareCount", 0),
                "collect_count": stats.get("collectCount", 0),
            },
            "video": {
                "duration": video.get("duration", 0),
                "ratio": video.get("ratio"),
                "width": video.get("width"),
                "height": video.get("height"),
                "cover": video.get("cover"),
                "dynamic_cover": video.get("dynamicCover"),
                "origin_cover": video.get("originCover"),
                "play_addr": video.get("playAddr"),
                "download_addr": video.get("downloadAddr"),
                "format": video.get("format"),
                "bitrate": video.get("bitrate"),
            },
            "images": images,
            "music": {
                "id": music.get("id"),
                "title": music.get("title"),
                "author": music.get("authorName"),
                "duration": music.get("duration"),
                "play_url": music.get("playUrl"),
                "cover": music.get("coverLarge") or music.get("coverMedium") or music.get("coverThumb"),
                "original": music.get("original", False),
            },
            "share_url": f"https://www.tiktok.com/@{author.get('uniqueId', '_')}/video/{it.get('id')}",
        }

    # ------------------------------------------------------------- 1. search videos
    async def search_videos(self, keyword: str, count: int = 15, offset: int = 0, region: str = "ID") -> Dict[str, Any]:
        url = (
            f"https://www.tiktok.com/api/search/general/full/?aid=1988&keyword={keyword}"
            f"&count={count}&offset={offset}&search_source=normal_search&query_correct_type=1"
            f"&is_filter_search=0&region={region}"
        )
        res = await engine.evaluate(JS_FETCH_JSON, url)
        if not res.get("ok"):
            return {
                "status_code": res.get("status", 0),
                "keyword": keyword,
                "count": 0,
                "videos": [],
                "error": res.get("error", "empty_response"),
            }
        data = res.get("json", {}) or {}
        items = [
            self._clean_video_item(d.get("item", {}))
            for d in data.get("data", [])
            if d.get("type") == 1
        ]
        return {
            "status_code": data.get("status_code", 0),
            "keyword": keyword,
            "count": len(items),
            "cursor": data.get("cursor"),
            "has_more": bool(data.get("has_more")),
            "videos": items,
        }

    # -------------------------------------------------------------- 2. search users
    async def search_users(self, keyword: str, count: int = 10, offset: int = 0, region: str = "ID") -> Dict[str, Any]:
        url = (
            f"https://www.tiktok.com/api/search/general/full/?aid=1988&keyword={keyword}"
            f"&count={count}&offset={offset}&search_source=normal_search&query_correct_type=1"
            f"&is_filter_search=0&type=4&region={region}"
        )
        res = await engine.evaluate(JS_FETCH_JSON, url)
        if not res.get("ok"):
            return {
                "status_code": res.get("status", 0),
                "keyword": keyword,
                "count": 0,
                "users": [],
                "error": res.get("error", "empty_response"),
            }
        data = res.get("json", {}) or {}
        users = []
        for d in data.get("data", []):
            if d.get("type") == 4:
                for u in d.get("user_list", []):
                    info = u.get("user_info", {})
                    users.append({
                        "uid": info.get("uid"),
                        "unique_id": info.get("unique_id"),
                        "nickname": info.get("nickname"),
                        "avatar": info.get("avatar_thumb"),
                        "signature": info.get("signature", ""),
                        "verified": bool(info.get("custom_verify") or info.get("enterprise_verify_reason")),
                        "follower_count": info.get("follower_count", 0),
                        "total_favorited": info.get("total_favorited", 0),
                        "sec_uid": info.get("sec_uid"),
                        "profile_url": f"https://www.tiktok.com/@{info.get('unique_id')}",
                    })
        return {
            "status_code": data.get("status_code", 0),
            "keyword": keyword,
            "count": len(users),
            "users": users,
        }

    # -------------------------------------------------------------- 3. user profile
    async def get_user_profile(self, username: str) -> Dict[str, Any]:
        username = username.lstrip("@").strip()
        scope = await engine.fetch_scope(f"https://www.tiktok.com/@{username}")
        if not scope or "webapp.user-detail" not in scope:
            return {
                "status": "error",
                "message": f"User '@{username}' not found or profile is restricted."
            }
        detail = scope.get("webapp.user-detail", {})
        user = detail.get("userInfo", {}).get("user", {})
        if not detail or not user or not user.get("uniqueId"):
            return {
                "status": "error",
                "message": f"User '@{username}' not found or profile is restricted."
            }
        stats = detail.get("userInfo", {}).get("stats", {})
        share = detail.get("shareMeta", {})

        return {
            "status": "ok",
            "user": {
                "id": user.get("id"),
                "unique_id": user.get("uniqueId"),
                "nickname": user.get("nickname"),
                "avatar_larger": user.get("avatarLarger"),
                "avatar_medium": user.get("avatarMedium"),
                "avatar_thumb": user.get("avatarThumb"),
                "signature": user.get("signature", ""),
                "verified": user.get("verified", False),
                "sec_uid": user.get("secUid"),
                "private_account": user.get("privateAccount", False),
                "relation": user.get("relation", 0),
                "bio_link": user.get("bioLink", {}).get("link") if isinstance(user.get("bioLink"), dict) else None,
                "profile_url": f"https://www.tiktok.com/@{user.get('uniqueId')}",
            },
            "stats": {
                "follower_count": stats.get("followerCount", 0),
                "following_count": stats.get("followingCount", 0),
                "heart_count": stats.get("heart") or stats.get("heartCount", 0),
                "video_count": stats.get("videoCount", 0),
                "digg_count": stats.get("diggCount", 0),
                "friend_count": stats.get("friendCount", 0),
            },
            "share_meta": {
                "title": share.get("title"),
                "desc": share.get("desc"),
            }
        }

    # --------------------------------------------------------------- 4. user videos
    async def get_user_videos(self, username: str, count: int = 20, region: str = "ID") -> Dict[str, Any]:
        """Fetch videos authored by a specific user."""
        username = username.lstrip("@").strip()
        search_result = await self.search_videos(keyword=f"@{username}", count=50, region=region)
        all_vids = search_result.get("videos", [])
        authored = [v for v in all_vids
                    if (v.get("author", {}).get("unique_id") or "").lower() == username.lower()]
        if not authored and all_vids:
            authored = all_vids

        return {
            "status": "ok",
            "username": username,
            "count": len(authored[:count]),
            "exact_matches": len([v for v in authored
                                  if (v.get("author", {}).get("unique_id") or "").lower() == username.lower()]),
            "videos": authored[:count],
        }


    # -------------------------------------------------------------- 5. video detail
    async def get_video_detail(self, video_id_or_url: str) -> Dict[str, Any]:
        vid_match = re.search(r"(\d{15,22})", str(video_id_or_url))
        if not vid_match:
            return {"status": "error", "message": "Invalid video ID or URL format."}
        video_id = vid_match.group(1)

        scope = await engine.fetch_scope(f"https://www.tiktok.com/@_/video/{video_id}")
        if not scope or "webapp.video-detail" not in scope:
            return {
                "status": "error",
                "message": f"Video '{video_id}' not found, deleted, or restricted."
            }
        vd = scope.get("webapp.video-detail", {})
        item = vd.get("itemInfo", {}).get("itemStruct", {})
        if not item:
            return {
                "status": "error",
                "message": f"Video '{video_id}' itemStruct empty."
            }
        cleaned = self._clean_video_item(item)
        cleaned["status"] = "ok"
        return cleaned

    # ------------------------------------------------------------ 6. video comments
    async def get_video_comments(self, video_id: str, count: int = 20, cursor: int = 0, region: str = "ID") -> Dict[str, Any]:
        vid_match = re.search(r"(\d{15,22})", str(video_id))
        if vid_match:
            video_id = vid_match.group(1)

        url = f"https://www.tiktok.com/api/comment/list/?aid=1988&aweme_id={video_id}&count={count}&cursor={cursor}&region={region}"
        res = await engine.evaluate(JS_FETCH_JSON, url)
        if not res.get("ok"):
            return {
                "status_code": res.get("status", 0),
                "video_id": video_id,
                "total": 0,
                "count": 0,
                "comments": [],
                "error": res.get("error", "empty_response"),
            }
        raw = res.get("json", {}) or {}
        comments = []
        for c in raw.get("comments", []):
            comments.append({
                "cid": c.get("cid"),
                "text": c.get("text"),
                "create_time": c.get("create_time"),
                "digg_count": c.get("digg_count", 0),
                "reply_total": c.get("reply_comment_total", 0),
                "author": {
                    "uid": c.get("user", {}).get("uid"),
                    "unique_id": c.get("user", {}).get("unique_id"),
                    "nickname": c.get("user", {}).get("nickname"),
                    "avatar": (c.get("user", {}).get("avatar_thumb", {}).get("url_list", []) or [None])[0],
                }
            })
        return {
            "status_code": raw.get("status_code", 0),
            "video_id": video_id,
            "total": raw.get("total", len(comments)),
            "count": len(comments),
            "cursor": raw.get("cursor"),
            "has_more": bool(raw.get("has_more")),
            "comments": comments,
        }

    # ------------------------------------------------------------- 7. trending feed
    async def get_trending_feed(self, count: int = 15, region: str = "ID") -> Dict[str, Any]:
        url = f"https://www.tiktok.com/api/recommend/item_list/?aid=1988&count={count}&region={region}"
        res = await engine.evaluate(JS_FETCH_JSON, url)
        if not res.get("ok"):
            return {
                "status_code": res.get("status", 0),
                "count": 0,
                "videos": [],
                "error": res.get("error", "empty_response"),
            }
        raw = res.get("json", {}) or {}
        items = [self._clean_video_item(it) for it in raw.get("itemList", [])]
        return {
            "status_code": raw.get("status_code", 0),
            "count": len(items),
            "has_more": bool(raw.get("hasMore")),
            "videos": items,
        }

    # ------------------------------------------------------------- 8. video download
    async def proxy_video_stream(self, video_url: str, range_header: Optional[str] = None):
        cookies = await engine.get_cookies()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Referer": "https://www.tiktok.com/",
            "Origin": "https://www.tiktok.com",
            "Accept": "*/*",
        }
        if range_header:
            headers["Range"] = range_header

        client = httpx.AsyncClient(cookies=cookies, headers=headers, timeout=60.0, follow_redirects=True)
        req = client.build_request("GET", video_url)
        resp = await client.send(req, stream=True)
        return resp, client


service = TikTokService()

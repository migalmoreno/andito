import html as _html
import json
import os
import re
from datetime import datetime
from typing import Literal, NotRequired, TypedDict
from urllib.parse import quote, urljoin, urlparse

from flask import request
from gallery_dl import job
from gallery_dl.exception import GalleryDLException
from gallery_dl.extractor import find as find_extractor

from .utils import fnv1a as _fnv1a


def download_post(url):
    extractor = find_extractor(url)
    data_job = job.DataJob(extractor, file=None)
    with open(os.devnull, "w") as f:
        data_job.file = f
        data_job.run()

    if data_job.exception:
        raise data_job.exception

    error_entry = next((d[1] for d in data_job.data if d[0] == -1), None)
    if error_entry:
        raise GalleryDLException(error_entry["message"])

    if not data_job.data_meta and not data_job.data_post:
        exc = GalleryDLException(f"No content returned for {url}")
        exc.status = 502
        raise exc

    cookies = {}
    http_headers = {}
    if extractor is not None and extractor.session is not None:
        cookies = {c.name: c.value for c in extractor.session.cookies}
        http_headers = dict(extractor.session.headers)

    return {
        "metadata": data_job.data_meta,
        "post": data_job.data_post,
        "urls": data_job.data_urls,
        "cookies": cookies,
        "http_headers": http_headers,
    }


class GalleryItem(TypedDict):
    thumbnail: NotRequired[str | None]
    url: NotRequired[str | None]
    authorName: NotRequired[str]
    authorThumbnail: NotRequired[str]
    authorUrl: NotRequired[str]
    groupName: NotRequired[str]
    groupThumbnail: NotRequired[str]
    groupUrl: NotRequired[str]


class GalleryResponse(TypedDict):
    renderer: Literal["gallery"]
    items: list[GalleryItem]
    searchable: NotRequired[bool]


class ImageStats(TypedDict):
    likes: NotRequired[int]
    plays: NotRequired[int]
    comments: NotRequired[int]
    shares: NotRequired[int]
    score: NotRequired[int]
    saves: NotRequired[int]


class ImageResponse(TypedDict):
    renderer: Literal["image"]
    url: str
    videoUrl: NotRequired[str]
    posterUrl: NotRequired[str]
    type: NotRequired[str]
    description: NotRequired[str]
    authorName: NotRequired[str]
    authorUrl: NotRequired[str]
    authorThumbnail: NotRequired[str]
    date: NotRequired[str]
    filename: NotRequired[str]
    groupName: NotRequired[str]
    groupThumbnail: NotRequired[str]
    groupUrl: NotRequired[str]
    stats: NotRequired[ImageStats]
    width: NotRequired[int]
    height: NotRequired[int]


class UserInfoStats(TypedDict):
    followers: NotRequired[int]
    following: NotRequired[int]
    mediaCount: NotRequired[int]
    likeCount: NotRequired[int]


class UserInfoResponse(TypedDict):
    renderer: Literal["user-info"]
    name: NotRequired[str]
    thumbnail: NotRequired[str]
    verified: NotRequired[bool]
    bio: NotRequired[str]
    nickname: NotRequired[str]
    category: NotRequired[str]
    private: NotRequired[bool]
    stats: NotRequired[UserInfoStats]


class UserProfileResponse(TypedDict):
    renderer: Literal["user-profile"]
    avatarUrl: NotRequired[str | None]
    galleryUrl: NotRequired[str | None]


class BoardItem(TypedDict):
    name: NotRequired[str]
    thumbnail: NotRequired[str]
    url: str
    count: NotRequired[int]
    score: NotRequired[int]
    date: NotRequired[str]
    description: NotRequired[str]
    groupName: NotRequired[str]
    groupUrl: NotRequired[str]
    groupThumbnail: NotRequired[str]


class GroupBoardResponse(TypedDict):
    renderer: Literal["group-board"]
    items: list[BoardItem]


class MediaBoardResponse(TypedDict):
    renderer: Literal["media-board"]
    items: list[BoardItem]
    columns: NotRequired[int]
    searchable: NotRequired[bool]


class ThreadPost(TypedDict):
    no: NotRequired[int]
    title: NotRequired[str]
    com: NotRequired[str]
    name: NotRequired[str]
    authorUrl: NotRequired[str]
    date: NotRequired[str]
    thumbnail: NotRequired[str]
    url: NotRequired[str]
    mediaType: NotRequired[str]
    sourceUrl: NotRequired[str]
    postUrl: NotRequired[str]
    repliesUrl: NotRequired[str]
    score: NotRequired[int]
    count: NotRequired[int]
    groupName: NotRequired[str]
    groupUrl: NotRequired[str]
    groupThumbnail: NotRequired[str]
    filename: NotRequired[str]
    resto: NotRequired[int]


class ThreadResponse(TypedDict):
    renderer: Literal["thread"]
    items: list[ThreadPost]
    nextUrl: NotRequired[str]


NormalizedResponse = (
    GalleryResponse
    | ImageResponse
    | GroupBoardResponse
    | MediaBoardResponse
    | ThreadResponse
    | UserInfoResponse
    | UserProfileResponse
)


def _normalize_27b9c082_67b6f7ae(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    return {
        "renderer": "gallery",
        "items": [
            {
                "thumbnail": (post.get("thumbnail") or {}).get("original"),
                "url": post.get("url"),
            }
            for post in meta
        ],
    }


def _normalize_27b9c082_4b1b2ee4(data, base_url, url, sub_hash) -> ImageResponse | dict:
    meta = data.get("metadata", [])
    if not meta:
        return {}
    post = meta[0]
    return {
        "renderer": "image",
        "url": post["thumbnail"]["original"],
        "description": post.get("content"),
        "authorName": post["creator"]["vanity"],
        "authorUrl": post["creator"]["url"],
        "authorThumbnail": post["campaign"]["avatar_photo_url"],
        **(
            {"width": post.get("width"), "height": post.get("height")}
            if post.get("width") and post.get("height")
            else {}
        ),
    }


def _normalize_5c6e7131_9d8e01de(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    if not any(post.get("id") for post in meta):
        sub_urls = data.get("urls", [])
        if sub_urls:
            data = download_post(sub_urls[0])
            meta = data.get("metadata", [])
    return {
        "renderer": "gallery",
        "items": [
            {
                "thumbnail": post.get("url"),
                "url": f"{base_url}/photo/?fbid={post['id']}&set={post['set_id']}",
            }
            for post in meta
            if post.get("id")
        ],
    }


def _normalize_5c6e7131_dc1d7def(data, base_url, url, sub_hash) -> ImageResponse | dict:
    meta = data.get("metadata", [])
    if not meta:
        return {}
    post = meta[0]
    return {
        "renderer": "image",
        "url": post.get("url"),
        "description": post.get("caption"),
        "date": post.get("date"),
        "authorName": post.get("username"),
        "authorUrl": f"{base_url}/{post['user_id']}",
        **(
            {"width": post.get("width"), "height": post.get("height")}
            if post.get("width") and post.get("height")
            else {}
        ),
    }


def _normalize_e88db17b_a3848f58(data, base_url, url, sub_hash) -> UserProfileResponse:
    urls = data.get("urls", [])
    return {
        "renderer": "user-profile",
        "avatarUrl": next((u for u in urls if "info" in u), None),
        "galleryUrl": next((u for u in urls if "posts" in u), None),
    }


def _normalize_e88db17b_7f691ebf(
    data, base_url, url, sub_hash
) -> UserInfoResponse | dict:
    posts = data.get("post", [])
    if not posts:
        return {}
    p = posts[0]
    return {
        "renderer": "user-info",
        "name": p.get("username"),
        "thumbnail": p.get("profile_pic_url_hd"),
        "category": p.get("category_name"),
        "bio": p.get("biography"),
        "private": p.get("is_private"),
        "nickname": p.get("full_name"),
        "stats": {
            "mediaCount": (p.get("edge_owner_to_timeline_media") or {}).get("count"),
            "followers": (p.get("edge_followed_by") or {}).get("count"),
            "following": (p.get("edge_follow") or {}).get("count"),
        },
    }


def _normalize_e88db17b_cf001e7a(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    urls = data.get("urls", [])
    return {
        "renderer": "gallery",
        "items": [
            {
                "thumbnail": urls[i] if i < len(urls) else None,
                "url": urls[i] if i < len(urls) else None,
            }
            for i, _ in enumerate(meta)
        ],
    }


def _normalize_f3a30c28_3418ee8b(data, base_url, url, sub_hash) -> UserProfileResponse:
    urls = data.get("urls", [])
    return {
        "renderer": "user-profile",
        "avatarUrl": next((u for u in urls if "avatar" in u), None),
        "galleryUrl": next((u for u in urls if "gallery" in u), None),
    }


def _normalize_f3a30c28_246f9606(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    urls = data.get("urls", [])
    return {
        "renderer": "gallery",
        "items": [
            {
                "thumbnail": urls[i] if i < len(urls) else None,
                "url": f"{base_url}/{post['user']}/{'video' if post.get('video') else 'media'}/{post['id']}",
            }
            for i, post in enumerate(meta)
        ],
    }


def _normalize_f3a30c28_6b6a3fc1(data, base_url, url, sub_hash) -> UserInfoResponse:
    meta = data.get("metadata", [])
    urls = data.get("urls", [])
    return {
        "renderer": "user-info",
        "name": meta[0].get("user") if meta else None,
        "thumbnail": urls[0] if urls else None,
    }


def _normalize_f3a30c28_77240af5(data, base_url, url, sub_hash) -> ImageResponse | dict:
    meta = data.get("metadata", [])
    if not meta:
        return {}
    m = meta[0]
    posts = data.get("post", [])
    p = posts[0] if posts else {}
    urls = data.get("urls", [])
    return {
        "renderer": "image",
        "url": urls[0] if urls else None,
        "authorName": p.get("user"),
        "filename": m.get("filename"),
        "date": m.get("date"),
        "description": m.get("description"),
        "authorUrl": f"{base_url}/{p.get('user')}",
        **(
            {"width": m.get("width"), "height": m.get("height")}
            if m.get("width") and m.get("height")
            else {}
        ),
    }


def _normalize_c0d3c7b1_1776446d(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    return {
        "renderer": "gallery",
        "items": [
            {
                "thumbnail": post.get("url"),
                "url": f"{base_url}/pin/{post['id']}",
                "authorName": post["pinner"]["username"],
                "authorThumbnail": post["pinner"]["image_small_url"],
                "authorUrl": f"{base_url}/{post['pinner']['username']}",
                "groupName": (post.get("board") or {}).get("name"),
                "groupThumbnail": (post.get("board") or {}).get("image_cover_url"),
                "groupUrl": (
                    f"{base_url}{post['board']['url']}" if post.get("board") else None
                ),
            }
            for post in meta
        ],
    }


def _normalize_c0d3c7b1_1692405e(data, base_url, url, sub_hash) -> GroupBoardResponse:
    meta = data.get("metadata", [])
    return {
        "renderer": "group-board",
        "items": [
            {
                "name": post.get("name"),
                "thumbnail": post.get("image_cover_url"),
                "url": f"{base_url}{post['url']}",
                "count": post.get("pin_count"),
                "date": post.get("created_at"),
            }
            for post in meta
        ],
    }


def _normalize_c0d3c7b1_22c9473f(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    return {
        "renderer": "gallery",
        "items": [
            {
                "thumbnail": post.get("url"),
                "url": f"{base_url}{post['seo_url']}",
            }
            for post in meta
        ],
    }


def _normalize_c0d3c7b1_e3df3be0(data, base_url, url, sub_hash) -> ImageResponse | dict:
    meta = data.get("metadata", [])
    if not meta:
        return {}
    post = meta[0]
    api_url = request.host_url.rstrip("/")
    return {
        "renderer": "image",
        "url": f"{api_url}/api/v1/proxy?url={post['url']}",
        "authorName": post["pinner"]["username"],
        "authorThumbnail": post["pinner"]["image_small_url"],
        "authorUrl": f"{base_url}/{post['pinner']['username']}",
        "description": post.get("description"),
        "date": post.get("created_at"),
        "groupName": post["board"]["name"],
        "groupThumbnail": post["board"]["image_cover_url"],
        "groupUrl": f"{base_url}{post['board']['url']}",
        **(
            {"width": post.get("width"), "height": post.get("height")}
            if post.get("width") and post.get("height")
            else {}
        ),
    }


def _normalize_ce200ea0_404ea5a3(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    items = [
        {
            "thumbnail": urljoin(
                f"{(p := urlparse(post['url'])).scheme}://{p.netloc}/",
                post["thumbnail_path"],
            ),
            "url": f"{base_url}/{post['creator']}/{post['id']}",
            "authorName": post.get("creator"),
            "authorThumbnail": (post.get("profile") or {}).get("profile_pic"),
            "authorUrl": f"{base_url}/{post.get('creator')}",
        }
        for post in meta
    ]
    return {
        "renderer": "gallery",
        **({"searchable": False} if sub_hash in ("36c7e141", "1601e678") else {}),
        "items": items,
    }


def _normalize_ce200ea0_5262c92a(data, base_url, url, sub_hash) -> ImageResponse | dict:
    meta = data.get("metadata", [])
    if not meta:
        return {}
    m = meta[0]
    posts = data.get("post", [])
    p = posts[0] if posts else {}
    return {
        "renderer": "image",
        "url": p.get("url"),
        "videoUrl": p.get("url"),
        "type": "video" if m.get("extension") in ("mp4", "mov") else "image",
        "filename": p.get("filename"),
        "description": m.get("description"),
        "authorName": p.get("creator"),
        "authorUrl": f"{base_url}/{p.get('creator')}",
        **(
            {"width": m.get("width"), "height": m.get("height")}
            if m.get("width") and m.get("height")
            else {}
        ),
    }


def _normalize_b8d92073_f374b090(data, base_url, url, sub_hash) -> UserProfileResponse:
    urls = data.get("urls", [])
    return {
        "renderer": "user-profile",
        "avatarUrl": next((u for u in urls if "avatar" in u), None),
        "galleryUrl": next((u for u in urls if "posts" in u), None),
    }


def _normalize_b8d92073_af675fda(data, base_url, url, sub_hash) -> UserInfoResponse:
    posts = data.get("post", [])
    urls = data.get("urls", [])
    p = posts[0] if posts else {}
    return {
        "renderer": "user-info",
        "name": p.get("nickname"),
        "thumbnail": urls[0] if urls else None,
        "bio": p.get("signature"),
        "verified": p.get("verified"),
    }


def _normalize_b8d92073_70206412(data, base_url, url, sub_hash) -> GalleryResponse:
    meta = data.get("metadata", [])
    posts = data.get("post", [])
    return {
        "renderer": "gallery",
        "items": [
            {
                "thumbnail": (post.get("video") or {}).get("cover"),
                "url": f"{base_url}/@{post['user']}/{'video' if i < len(meta) and meta[i].get('type') == 'video' else 'photo'}/{post['id']}",
            }
            for i, post in enumerate(posts)
        ],
    }


def _normalize_03bfedaf_e7d2ac0d(data, base_url, url, sub_hash) -> MediaBoardResponse:
    meta = data.get("metadata", [])
    urls = data.get("urls", [])
    return {
        "renderer": "media-board",
        "items": [
            {
                "url": urls[i],
                "name": m.get("sub") or f"#{m['no']}",
                "description": (
                    _html.unescape(re.sub(r"<[^>]+>", " ", m["com"])).strip()
                    if m.get("com")
                    else None
                ),
                "count": m.get("replies"),
                "date": datetime.utcfromtimestamp(m["last_modified"]).isoformat() + "Z",
                "thumbnail": (
                    f"https://i.4cdn.org/{m['board']}/{m['tim']}s.jpg"
                    if m.get("tim")
                    else None
                ),
            }
            for i, m in enumerate(meta)
            if i < len(urls)
        ],
    }


def _normalize_03bfedaf_25ba7f3f(data, base_url, url, sub_hash) -> ThreadResponse:
    meta = data.get("metadata", [])
    urls = data.get("urls", [])
    return {
        "renderer": "thread",
        "items": [
            {
                "no": m.get("no"),
                "com": m.get("com"),
                "name": m.get("name"),
                "date": (
                    datetime.utcfromtimestamp(m["time"]).isoformat() + "Z"
                    if m.get("time")
                    else None
                ),
                "thumbnail": (
                    f"https://i.4cdn.org/{m['board']}/{m['tim']}s.jpg"
                    if m.get("tim")
                    else None
                ),
                "url": urls[i] if i < len(urls) and urls[i] else None,
                "filename": (
                    f"{m['filename']}{m['ext']}"
                    if m.get("filename") and m.get("ext")
                    else None
                ),
                "resto": m.get("resto"),
            }
            for i, m in enumerate(meta)
        ],
    }


def _normalize_bd300ce5_2493dc95(data, base_url, url, sub_hash) -> MediaBoardResponse:
    meta = data.get("metadata", [])
    urls = data.get("urls", [])
    return {
        "renderer": "media-board",
        "columns": 1,
        **({"searchable": False} if sub_hash == "2c906dae" else {}),
        "items": [
            {
                "url": urls[i] if i < len(urls) else None,
                "name": m.get("title"),
                "thumbnail": next(
                    (
                        v
                        for v in [
                            _html.unescape(
                                (
                                    ((m.get("preview") or {}).get("images") or [{}])[
                                        0
                                    ].get("source")
                                    or {}
                                ).get("url", "")
                            )
                            or None,
                            (
                                m.get("thumbnail")
                                if (m.get("thumbnail") or "").startswith("https://")
                                else None
                            ),
                        ]
                        if v
                    ),
                    None,
                ),
                "description": (m.get("selftext")[:200] if m.get("selftext") else None),
                "count": m.get("num_comments"),
                "score": m.get("score"),
                "date": (
                    datetime.utcfromtimestamp(m["created_utc"]).isoformat() + "Z"
                    if m.get("created_utc")
                    else None
                ),
                "groupName": (f"r/{m['subreddit']}" if m.get("subreddit") else None),
                "groupUrl": (
                    f"{base_url}/r/{m['subreddit']}" if m.get("subreddit") else None
                ),
            }
            for i, m in enumerate(meta)
        ],
    }


def _normalize_bd300ce5_578a8689(data, base_url, url, sub_hash) -> ThreadResponse:
    meta = data.get("metadata", [])
    urls = [u for u in data.get("urls", []) if not u.startswith("ytdl:")]
    is_comment_url = bool(re.search(r"/comments/[^/?#]+/[^/?#]+/[^/?#]+", url))
    sub_id_match = re.search(r"/comments/([a-z0-9]+)", url)
    sub_id = sub_id_match.group(1) if sub_id_match else ""
    fc_match = (
        re.search(r"/comments/[^/?#]+/[^/?#]+/([a-z0-9]+)", url)
        if is_comment_url
        else None
    )
    focused_comment_id = fc_match.group(1) if fc_match else ""
    items = []
    listing_cursor = None
    listing_cursor_type = None
    for i, m in enumerate(meta):
        if m.get("gdl_cursor"):
            listing_cursor = m.get("gdl_cursor_val")
            listing_cursor_type = m["gdl_cursor"]
            continue
        if m.get("_reddit_type") == "submission" or m.get("title"):
            if is_comment_url:
                continue
            title = m.get("title", "")
            selftext_html = re.sub(
                r"<!--.*?-->", "", _html.unescape(m.get("selftext_html") or "")
            ).strip()
            com = selftext_html or None
            thumbnail = next(
                (
                    v
                    for v in [
                        _html.unescape(
                            (
                                ((m.get("preview") or {}).get("images") or [{}])[0].get(
                                    "source"
                                )
                                or {}
                            ).get("url", "")
                        )
                        or None,
                        (
                            m.get("thumbnail")
                            if (m.get("thumbnail") or "").startswith("https://")
                            else None
                        ),
                    ]
                    if v
                ),
                None,
            )
            sub_url = m.get("url", "")
            if m.get("is_video"):
                reddit_video = (m.get("media") or {}).get("reddit_video") or {}
                media_url = (
                    reddit_video.get("fallback_url")
                    or reddit_video.get("hls_url")
                    or None
                )
                media_type = "video"
                source_url = None
            elif sub_url.startswith("https://i.redd.it/"):
                media_url = sub_url
                media_type = "image"
                source_url = None
            elif sub_url and not m.get("is_self") and "reddit.com" not in sub_url:
                media_url = None
                media_type = None
                source_url = sub_url
            else:
                media_url = None
                media_type = None
                source_url = None
            author = m.get("author")
            subreddit = m.get("subreddit")
            items.append(
                {
                    "title": title or None,
                    "com": com,
                    "name": author,
                    "authorUrl": (f"{base_url}/user/{author}" if author else None),
                    "date": (
                        datetime.utcfromtimestamp(m["created_utc"]).isoformat() + "Z"
                        if m.get("created_utc")
                        else None
                    ),
                    "thumbnail": thumbnail,
                    "url": media_url,
                    "mediaType": media_type,
                    "sourceUrl": source_url,
                    "postUrl": url,
                    "score": m.get("score"),
                    "count": m.get("num_comments"),
                    "groupName": f"r/{subreddit}" if subreddit else None,
                    "groupUrl": (f"{base_url}/r/{subreddit}" if subreddit else None),
                }
            )
        else:
            parent_id = m.get("parent_id", "")
            if is_comment_url:
                if m.get("id") == focused_comment_id:
                    continue
                if parent_id != "t1_" + focused_comment_id:
                    continue
            else:
                if not parent_id.startswith("t3_"):
                    continue
            body_html = re.sub(
                r"<!--.*?-->", "", _html.unescape(m.get("body_html") or "")
            ).strip()
            if not body_html:
                continue
            author = m.get("author")
            subreddit = m.get("subreddit", "")
            comment_id = m.get("id", "")
            permalink = m.get("permalink") or (
                f"/r/{subreddit}/comments/{sub_id}/_/{comment_id}/"
                if subreddit and sub_id and comment_id
                else None
            )
            has_replies = bool(m.get("replies"))
            items.append(
                {
                    "com": body_html,
                    "name": author,
                    "authorUrl": (f"{base_url}/user/{author}" if author else None),
                    "date": (
                        datetime.utcfromtimestamp(m["created_utc"]).isoformat() + "Z"
                        if m.get("created_utc")
                        else None
                    ),
                    "score": m.get("score"),
                    "repliesUrl": (
                        f"{base_url}{permalink}" if permalink and has_replies else None
                    ),
                }
            )
    next_url = None
    if is_comment_url and listing_cursor:
        base_comment_url = url.split("?")[0]
        if listing_cursor_type == "after":
            next_url = f"{base_comment_url}?after={listing_cursor}"
        else:
            next_url = f"{base_comment_url}?children={listing_cursor}"
    return {
        "renderer": "thread",
        "items": items,
        **({"nextUrl": next_url} if next_url else {}),
    }


def _normalize_b8d92073_33295e95(data, base_url, url, sub_hash) -> ImageResponse | dict:
    meta = data.get("metadata", [])
    posts = data.get("post", [])
    urls = data.get("urls", [])
    if not posts or not meta:
        return {}
    p = posts[0]
    m = meta[0]
    cookies = data.get("cookies", {})
    http_headers = data.get("http_headers", {})
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = {**http_headers, **({"Cookie": cookie_str} if cookie_str else {})}
    api_url = request.host_url.rstrip("/")
    video_url = (
        f"{api_url}/api/v1/proxy?headers={quote(json.dumps(headers))}&url={quote(urls[0])}"
        if urls
        else None
    )
    video = p.get("video") or {}
    raw_stats = p.get("stats") or {}
    width = video.get("width")
    height = video.get("height")
    stats = {
        k: v
        for k, v in {
            "likes": raw_stats.get("diggCount"),
            "plays": raw_stats.get("playCount"),
            "comments": raw_stats.get("commentCount"),
            "shares": raw_stats.get("shareCount"),
        }.items()
        if v is not None
    }
    return {
        "renderer": "image",
        "url": video.get("cover"),
        "posterUrl": video.get("cover"),
        "videoUrl": video_url,
        "type": m.get("type"),
        "filename": m.get("filename"),
        "date": m.get("date"),
        "description": p.get("desc"),
        "authorName": p.get("user"),
        "authorUrl": f"{base_url}/@{p.get('user')}",
        "authorThumbnail": (p.get("author") or {}).get("avatarThumb"),
        **({"stats": stats} if stats else {}),
        **({"width": width, "height": height} if width and height else {}),
    }


_NORMALIZERS = {
    ("27b9c082", "67b6f7ae"): _normalize_27b9c082_67b6f7ae,
    ("27b9c082", "4b1b2ee4"): _normalize_27b9c082_4b1b2ee4,
    ("5c6e7131", "9d8e01de"): _normalize_5c6e7131_9d8e01de,
    ("5c6e7131", "dc1d7def"): _normalize_5c6e7131_dc1d7def,
    ("e88db17b", "a3848f58"): _normalize_e88db17b_a3848f58,
    ("e88db17b", "7f691ebf"): _normalize_e88db17b_7f691ebf,
    ("e88db17b", "cf001e7a"): _normalize_e88db17b_cf001e7a,
    ("f3a30c28", "3418ee8b"): _normalize_f3a30c28_3418ee8b,
    ("f3a30c28", "246f9606"): _normalize_f3a30c28_246f9606,
    ("f3a30c28", "6b6a3fc1"): _normalize_f3a30c28_6b6a3fc1,
    ("f3a30c28", "77240af5"): _normalize_f3a30c28_77240af5,
    ("c0d3c7b1", "1776446d"): _normalize_c0d3c7b1_1776446d,
    ("c0d3c7b1", "1692405e"): _normalize_c0d3c7b1_1692405e,
    ("c0d3c7b1", "22c9473f"): _normalize_c0d3c7b1_22c9473f,
    ("c0d3c7b1", "2b9db8bf"): _normalize_c0d3c7b1_22c9473f,
    ("c0d3c7b1", "e3df3be0"): _normalize_c0d3c7b1_e3df3be0,
    ("ce200ea0", "404ea5a3"): _normalize_ce200ea0_404ea5a3,
    ("ce200ea0", "36c7e141"): _normalize_ce200ea0_404ea5a3,
    ("ce200ea0", "1601e678"): _normalize_ce200ea0_404ea5a3,
    ("ce200ea0", "5262c92a"): _normalize_ce200ea0_5262c92a,
    ("b8d92073", "f374b090"): _normalize_b8d92073_f374b090,
    ("b8d92073", "af675fda"): _normalize_b8d92073_af675fda,
    ("b8d92073", "70206412"): _normalize_b8d92073_70206412,
    ("03bfedaf", "e7d2ac0d"): _normalize_03bfedaf_e7d2ac0d,
    ("03bfedaf", "25ba7f3f"): _normalize_03bfedaf_25ba7f3f,
    ("bd300ce5", "2493dc95"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "2c906dae"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "ba419d12"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "aac97454"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "3ce02945"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "e05a81c1"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "8366fc68"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "0160e943"): _normalize_bd300ce5_2493dc95,
    ("bd300ce5", "578a8689"): _normalize_bd300ce5_578a8689,
    ("b8d92073", "33295e95"): _normalize_b8d92073_33295e95,
}


def normalize(
    category, subcategory, data, base_url, url=""
) -> NormalizedResponse | dict | None:
    sub_hash = _fnv1a(category + subcategory)
    fn = _NORMALIZERS.get((_fnv1a(category), sub_hash))
    return fn(data, base_url, url, sub_hash) if fn else None

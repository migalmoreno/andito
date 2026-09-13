import logging
import random
import re as _re
import time
from urllib.parse import urlparse, parse_qs
from gallery_dl import config
from gallery_dl.extractor import extractors
from gallery_dl.extractor.common import Message
from gallery_dl import text as _gdl_text
from gallery_dl.extractor.reddit import RedditAPI as _RedditAPI
from .utils import fnv1a as _fnv1a

_by_key = {
    (
        _fnv1a(getattr(c, "category", "")),
        _fnv1a(getattr(c, "category", "") + getattr(c, "subcategory", "")),
    ): c
    for c in extractors()
}

_03bfedaf_25ba7f3f = _by_key.get(("03bfedaf", "25ba7f3f"))
_03bfedaf_e7d2ac0d = _by_key.get(("03bfedaf", "e7d2ac0d"))
_bd300ce5_2493dc95 = _by_key.get(("bd300ce5", "2493dc95"))
_bd300ce5_2c906dae = _by_key.get(("bd300ce5", "2c906dae"))
_bd300ce5_ba419d12 = _by_key.get(("bd300ce5", "ba419d12"))
_bd300ce5_578a8689 = _by_key.get(("bd300ce5", "578a8689"))

_board_root = ""
if _03bfedaf_e7d2ac0d:
    _p = urlparse(_03bfedaf_e7d2ac0d.example)
    _board_root = f"{_p.scheme}://{_p.netloc}"


def _patch_03bfedaf_25ba7f3f(self):
    posts = self.request_json(
        f"https://a.4cdn.org/{self.board}/thread/{self.thread}.json"
    )["posts"]
    title = posts[0].get("sub") or _gdl_text.remove_html(posts[0]["com"])
    data = {
        "board": self.board,
        "thread": self.thread,
        "title": _gdl_text.unescape(title)[:50],
    }
    yield Message.Directory, "", data
    for post in posts:
        post.update(data)
        if "filename" in post:
            post["extension"] = post["ext"][1:]
            post["filename"] = _gdl_text.unescape(post["filename"])
            yield Message.Url, f"https://i.4cdn.org/{post['board']}/{post['tim']}{post['ext']}", post
        else:
            yield Message.Url, "", post


def _patch_03bfedaf_e7d2ac0d(self):
    pages = self.request_json(f"https://a.4cdn.org/{self.board}/catalog.json")
    data = {"board": self.board}
    yield Message.Directory, "", data
    for page in pages:
        for thread in page.get("threads", []):
            thread["board"] = self.board
            thread["_extractor"] = _03bfedaf_25ba7f3f
            yield Message.Queue, f"{_board_root}/{self.board}/thread/{thread['no']}/", thread


def _patch_bd300ce5(self):
    self.api = _RedditAPI(self)
    yield Message.Directory, "", {}
    for submission, _ in self.submissions():
        if submission is None:
            continue
        sub_id = submission.get("id")
        if not sub_id:
            continue
        subreddit = submission.get("subreddit", "")
        yield Message.Queue, f"https://www.reddit.com/r/{subreddit}/comments/{sub_id}/", submission


def _patch_bd300ce5_578a8689(self):
    self.api = _RedditAPI(self)
    self.api.comments = 100
    yield Message.Directory, "", {}
    comment_match = _re.search(r"/comments/([a-z0-9]+)/[^/?#]*/([a-z0-9]+)", self.url)
    if comment_match:
        submission_id, comment_id = comment_match.group(1), comment_match.group(2)
        endpoint = f"/comments/{submission_id}/.json"
        link_id = "t3_" + submission_id
        qs = parse_qs(urlparse(self.url).query)
        if children_param := qs.get("children", [None])[0]:
            all_ids = children_param.split(",")
            batch, remaining = all_ids[:10], all_ids[10:]
            for comment in self.api.morechildren(link_id, batch):
                if not comment.get("body_html"):
                    continue
                comment["_reddit_type"] = "comment"
                yield Message.Url, "", comment
            if remaining:
                yield Message.Url, "", {
                    "gdl_cursor": "children",
                    "gdl_cursor_val": ",".join(remaining),
                }
        else:
            params = {"limit": self.api.comments, "comment": comment_id}
            _, focused = self.api._call(endpoint, params)
            # Walk the context chain to find the focused comment's "more" stub siblings
            more_ids = []
            _queue = list((focused.get("data") or {}).get("children") or [])
            while _queue:
                _item = _queue.pop(0)
                if _item.get("kind") == "more":
                    continue
                _data = _item.get("data") or {}
                if _data.get("id") == comment_id:
                    for _child in ((_data.get("replies") or {}).get("data") or {}).get(
                        "children"
                    ) or []:
                        if _child.get("kind") == "more":
                            more_ids.extend(
                                (_child.get("data") or {}).get("children") or []
                            )
                    break
                _replies = _data.get("replies")
                if isinstance(_replies, dict):
                    _queue.extend((_replies.get("data") or {}).get("children") or [])
            if more_ids:
                yield Message.Url, "", {
                    "gdl_cursor": "children",
                    "gdl_cursor_val": ",".join(more_ids),
                }
            for comment in self.api._flatten(focused, None):
                if not comment.get("body_html"):
                    continue
                comment["_reddit_type"] = "comment"
                yield Message.Url, "", comment
    else:
        for submission, comments in self.submissions():
            if submission is None:
                continue
            submission["_reddit_type"] = "submission"
            yield Message.Url, "", submission
            for comment in comments:
                if not comment.get("body_html"):
                    continue
                comment["_reddit_type"] = "comment"
                yield Message.Url, "", comment


for _cls, _fn in [
    (_03bfedaf_25ba7f3f, _patch_03bfedaf_25ba7f3f),
    (_03bfedaf_e7d2ac0d, _patch_03bfedaf_e7d2ac0d),
    (_bd300ce5_2493dc95, _patch_bd300ce5),
    (_bd300ce5_2c906dae, _patch_bd300ce5),
    (_bd300ce5_ba419d12, _patch_bd300ce5),
    (_bd300ce5_578a8689, _patch_bd300ce5_578a8689),
]:
    if _cls:
        _cls.items = _fn


_REDDIT_CLIENT_IDS = [
    "ohXpoqrZYub1kg",
    "6N9uN0krSDE-ig",
]
_REDDIT_ANDROID_VERSIONS = [
    "Version 2024.22.1/Build 1652272",
    "Version 2024.23.1/Build 1665606",
    "Version 2024.24.1/Build 1682520",
    "Version 2024.25.0/Build 1693595",
    "Version 2024.25.2/Build 1700401",
    "Version 2024.26.0/Build 1712645",
    "Version 2024.27.0/Build 1724716",
    "Version 2024.28.0/Build 1736729",
    "Version 2024.29.0/Build 1748758",
    "Version 2024.30.0/Build 1760827",
    "Version 2024.31.0/Build 1772896",
    "Version 2024.32.0/Build 1784965",
    "Version 2024.33.0/Build 1797034",
    "Version 2024.34.0/Build 1809103",
    "Version 2024.35.0/Build 1821172",
    "Version 2024.36.0/Build 1833241",
    "Version 2024.37.0/Build 1845310",
    "Version 2024.38.0/Build 1857379",
    "Version 2024.39.0/Build 1869448",
    "Version 2024.40.0/Build 1881517",
    "Version 2024.41.0/Build 1893586",
    "Version 2024.42.0/Build 1905655",
    "Version 2024.43.0/Build 1917724",
    "Version 2024.44.0/Build 1929793",
    "Version 2024.45.0/Build 2001943",
    "Version 2024.46.0/Build 2012731",
    "Version 2024.47.0/Build 2029755",
]
_reddit_rate_limited_at: dict[str, float] = {}
_current_reddit_client_id: str = _REDDIT_CLIENT_IDS[0]


class _RedditRateLimitHandler(logging.Handler):
    def emit(self, record):
        if "rate limit exceeded" in record.getMessage().lower():
            _reddit_rate_limited_at[_current_reddit_client_id] = time.monotonic()


logging.getLogger("gallery_dl.extractor.reddit").addHandler(_RedditRateLimitHandler())


def _best_reddit_client_id() -> str:
    global _current_reddit_client_id
    cid = min(_REDDIT_CLIENT_IDS, key=lambda c: _reddit_rate_limited_at.get(c, 0.0))
    _current_reddit_client_id = cid
    return cid


def _reddit_android_ua() -> str:
    version = random.choice(_REDDIT_ANDROID_VERSIONS)
    android = random.randint(9, 14)
    return f"Reddit/{version}/Android {android}"


_DISPATCH_INCLUDE_ALL_CATEGORIES = (
    "5c6e7131",
    "e88db17b",
    "b8d92073",
    "f3a30c28",
    "fb2fff6e",
)


def apply_extractor_config(category, subcategory, pagination):
    start, end = (int(x) for x in pagination.split("-"))
    page_size = end - start + 1

    if _fnv1a(category) in _DISPATCH_INCLUDE_ALL_CATEGORIES:
        config.set(("extractor", category), "include", "all")

    match (_fnv1a(category), _fnv1a(category + subcategory)):
        case ("e88db17b", _):
            config.set(("extractor",), "image-range", pagination)
        case ("b8d92073", "70206412"):
            config.set(("extractor", category, subcategory), "tiktok-range", pagination)
        case ("c0d3c7b1", "1692405e") | ("03bfedaf", "e7d2ac0d"):
            config.set(("extractor",), "chapter-range", pagination)
        case ("6987b443", sub) if sub in (
            "45c4d380",
            "d6cf21b3",
            "831a43a1",
            "6b424a7b",
        ):
            config.set(("extractor",), "chapter-range", pagination)
        case ("fb2fff6e", sub) if sub in (
            "494f3b89",
            "4ebd17e2",
            "25dd196e",
            "7d93564d",
            "651df0de",
            "69f3c98a",
        ):
            config.set(("extractor",), "post-range", pagination)
        case ("bd300ce5", sub) if sub in (
            "2493dc95",
            "2c906dae",
            "ba419d12",
            "aac97454",
            "3ce02945",
            "e05a81c1",
            "8366fc68",
            "0160e943",
        ):
            config.set(("extractor", "reddit"), "client-id", _best_reddit_client_id())
            config.set(
                ("extractor", "reddit"), "user-agent-oauth", _reddit_android_ua()
            )
            config.set(("extractor", "reddit"), "limit", page_size)
            config.set(("extractor",), "chapter-range", pagination)
        case ("bd300ce5", _):
            config.set(("extractor", "reddit"), "client-id", _best_reddit_client_id())
            config.set(
                ("extractor", "reddit"), "user-agent-oauth", _reddit_android_ua()
            )
            config.set(("extractor",), "image-range", pagination)
        case _:
            config.set(("extractor",), "image-range", pagination)

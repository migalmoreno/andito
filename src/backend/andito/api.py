import requests
import os
import json
import tempfile
from gallery_dl.exception import AbortExtraction, GalleryDLException, NotFoundError
from gallery_dl.extractor import extractors, find as find_extractor
from werkzeug.exceptions import HTTPException
from itertools import groupby
from gallery_dl import config
from flask import Blueprint, current_app, request, jsonify, make_response, Response
from urllib.parse import unquote, urlparse
from http import HTTPStatus

from . import extractors as _extractors_patch
from .extractors import apply_extractor_config, mark_reddit_client_id_failed
from .normalizers import download_post, normalize
from .utils import fnv1a as _fnv1a

_extractors = list(extractors())


api_v1 = Blueprint("API_v1", __name__)


@api_v1.after_request
def handle_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@api_v1.errorhandler(HTTPException)
def handle_http_exception(e):
    current_app.logger.exception(e)
    response = e.get_response()
    response.data = jsonify(
        {"code": e.code, "name": e.name, "description": e.description}
    )
    response.content_type = "application/json"
    return response


@api_v1.errorhandler(NotFoundError)
def handle_gallery_dl_not_found(e):
    current_app.logger.exception(e)
    return make_response(
        {
            "message": e.message,
            "status": 404,
        },
        404,
    )


@api_v1.errorhandler(GalleryDLException)
def handle_gallery_dl_exception(e):
    current_app.logger.exception(e)
    status = e.status if hasattr(e, "status") else 500
    return make_response(
        {
            "message": e.message,
            "status": status,
        },
        status,
    )


@api_v1.route("/health")
def health():
    return make_response()


@api_v1.route("/config", methods=["POST"])
def load_config():
    content = request.get_json()
    with tempfile.TemporaryDirectory() as base:
        config_path = os.path.join(base, "config")
        with open(config_path, "w") as fp:
            fp.write(json.dumps(content))

        config.load((config_path,))

    return make_response(content)


@api_v1.route("/proxy", methods=["GET", "POST", "OPTIONS", "HEAD"])
def proxy():
    url = ""
    if _url := request.args.get("url"):
        url = unquote(_url)

    extra_headers = {}
    if headers_arg := request.args.get("headers"):
        extra_headers = json.loads(headers_arg)

    allow_redirects = request.args.get("follow_redirects", "true").lower() != "false"

    res = requests.request(
        method=request.method,
        url=url,
        headers={
            k: v
            for k, v in request.headers
            if k.lower() not in {"host", "referer", "origin"}
        }
        | extra_headers,
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=allow_redirects,
    )
    content = res.content
    excluded = {"transfer-encoding", "content-encoding", "content-length", "set-cookie"}
    headers = [(k, v) for k, v in res.raw.headers.items() if k.lower() not in excluded]
    headers.append(("Content-Length", str(len(content))))
    return Response(content, res.status_code, headers)


_SEARCH_SUBCATEGORIES = {
    "aac97454": {
        "name": "subreddit-search",
        "example": "https://www.reddit.com/r/SUBREDDIT/search/?q=QUERY&restrict_sr=1",
        "groups": ["QUERY", "SUBREDDIT"],
    },
    "d04699c9": {
        "name": "search",
        "example": "https://www.reddit.com/search/?q=QUERY",
        "groups": ["QUERY"],
    },
    "e05a81c1": {
        "name": "user-search",
        "example": "https://www.reddit.com/user/USER/search/?q=QUERY",
        "groups": ["QUERY", "USER"],
    },
    "f3e9f8dc": {
        "name": "top",
        "example": "https://www.reddit.com/top/?t=FILTER",
        "groups": ["FILTER"],
        "filters": ["hour", "day", "week", "month", "year", "all"],
    },
    "0160e943": {
        "name": "subreddit-top",
        "example": "https://www.reddit.com/r/SUBREDDIT/top/?t=FILTER",
        "groups": ["/r/SUBREDDIT", None, None, "FILTER"],
        "filters": ["hour", "day", "week", "month", "year", "all"],
    },
}

_GROUPS_OVERRIDES = {
    ("4ef4b826", "c818bca6"): {
        "groups": ["QUERY"],
    },
    ("4ef4b826", "2c98502e"): {
        "url": "https://www.artstation.com/artwork?sorting=FILTER",
        "groups": ["FILTER"],
        "filters": ["trending", "latest", "popular", "community"],
    },
    ("f5884405", "9caaf4e9"): {
        "groups": ["QUERY"],
    },
    ("430e2afe", "6f82efae"): {
        "groups": ["QUERY"],
    },
}


def get_grouped_extractors():
    groups = []
    for k, g in groupby(_extractors, key=lambda ext: ext.basecategory or ext.category):
        exts = []
        for ext in g:
            normalized = normalize(ext.category, ext.subcategory, {}, "")
            if normalized is None:
                continue
            override = _GROUPS_OVERRIDES.get(
                (_fnv1a(k), _fnv1a(ext.category + ext.subcategory))
            )
            exts.append(
                {
                    "name": ext.subcategory,
                    "category": ext.basecategory or ext.category,
                    "example": ext.example,
                    "searchable": normalized.get("searchable", True),
                    "nsfw": normalized.get("nsfw", False),
                    **(
                        {"filters": override["filters"]}
                        if override and "filters" in override
                        else {}
                    ),
                }
            )
        if _fnv1a(k) == "bd300ce5" and exts:
            cat = exts[0]["category"]
            for sub in _SEARCH_SUBCATEGORIES.values():
                exts.append(
                    {
                        "name": sub["name"],
                        "category": cat,
                        "example": sub["example"],
                        "searchable": sub.get("searchable", True),
                        "nsfw": False,
                        **({"filters": sub["filters"]} if "filters" in sub else {}),
                    }
                )
        if exts:
            groups.append({"name": k, "subcategories": exts})

    return groups


@api_v1.route("/categories")
def get_categories():
    return make_response(get_grouped_extractors())


def get_extractors_by_category():
    groups = []
    for k, g in groupby(_extractors, key=lambda ext: ext.category or ext.basecategory):
        groups.append({"category": k, "subcategories": list(g)})
    return groups


@api_v1.route("/extractors")
def get_extractors():
    groups = get_extractors_by_category()

    category = None
    subcategory = None

    if cat := request.args.get("category"):
        category = cat
        subcategory = request.args.get("subcategory")
    elif url := request.args.get("url"):
        extractor = find_extractor(unquote(url))
        if extractor:
            category = extractor.category
            subcategory = extractor.subcategory

    if category and subcategory:
        sub_hash = _fnv1a(category + subcategory)
        if sub_hash in _SEARCH_SUBCATEGORIES:
            sub_info = _SEARCH_SUBCATEGORIES[sub_hash]
            ext_inst = find_extractor(sub_info["example"])
            return make_response(
                {
                    "category": category,
                    "subcategory": subcategory,
                    "url": sub_info["example"],
                    "groups": sub_info["groups"],
                    "configPath": ext_inst._cfgpath if ext_inst else [category],
                    **(
                        {"filters": sub_info["filters"]}
                        if "filters" in sub_info
                        else {}
                    ),
                }
            )

    for extractor_group in groups:
        if extractor_group["category"] == category:
            extractor = next(
                (
                    x
                    for x in extractor_group["subcategories"]
                    if x.subcategory == subcategory
                ),
                extractor_group["subcategories"][0],
            )
            if match := extractor.pattern.match(extractor.example):
                extractor_instance = extractor(match)
                override = _GROUPS_OVERRIDES.get(
                    (_fnv1a(category), _fnv1a(category + subcategory))
                )
                return make_response(
                    {
                        "category": category,
                        "subcategory": extractor.subcategory,
                        "url": (
                            override["url"]
                            if override and "url" in override
                            else extractor_instance.url
                        ),
                        "groups": (
                            override["groups"]
                            if override
                            else extractor_instance.groups
                        ),
                        "configPath": extractor_instance._cfgpath,
                        **(
                            {"filters": override["filters"]}
                            if override and "filters" in override
                            else {}
                        ),
                    }
                )

    return make_response("Not found", HTTPStatus.NOT_FOUND)


@api_v1.route("/posts/<path:url>")
def posts(url=""):
    items_per_page = request.args.get("limit", default=10, type=int)
    pagination_start = request.args.get("skip", default=0, type=int) + 1
    pagination_end = pagination_start + items_per_page - 1
    parsed_url = unquote(url)
    extractor = find_extractor(parsed_url)

    if extractor:
        apply_extractor_config(
            extractor._cfgpath[1],
            extractor._cfgpath[2],
            f"{pagination_start}-{pagination_end}",
        )

    try:
        post = download_post(parsed_url)
    except AbortExtraction:
        if extractor and _fnv1a(extractor.category) == "bd300ce5":
            mark_reddit_client_id_failed()
        raise

    if extractor:
        category, subcategory = extractor._cfgpath[1], extractor._cfgpath[2]
        base_url = f"{urlparse(parsed_url).scheme}://{urlparse(parsed_url).netloc}"
        normalized = normalize(category, subcategory, post, base_url, parsed_url)
        if normalized is not None:
            return make_response(normalized)

    return make_response(post)

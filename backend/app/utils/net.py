from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse


def extract_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).netloc
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def infer_source_type(domain: Optional[str]) -> str:
    if not domain:
        return "unknown"
    d = domain.lower()

    if any(m in d for m in ("2gis", "openstreetmap", "osm.org")):
        return "map"
    if "google.com/maps" in d or "yandex.ru/maps" in d:
        return "map"

    social = (
        "vk.com", "vk.ru", "t.me", "telegram", "instagram.com", "facebook.com",
        "tiktok.com", "youtube.com", "youtu.be", "twitter.com", "x.com",
    )
    if any(d == s or d.endswith("." + s) for s in social):
        return "social"

    reviews = ("otzovik.com", "irecommend", "flamp", "yell.ru", "zoon.ru", "prodoctorov")
    if any(s in d for s in reviews):
        return "review"

    directories = (
        "zoon.ru", "yell.ru", "spr.ru", "prodoctorov.ru", "flamp.ru",
        "2gis.ru", "direktoria", "rusprofile", "otzyv", "irecommend",
        "spravnik", "tamaly", "afisha", "yellowpages",
    )
    if any(s in d for s in directories):
        return "directory"

    forums = ("forum", "otvet.mail.ru", "vc.ru", "habr.com", "pikabu.ru", "drom.ru")
    if any(s in d for s in forums):
        return "forum"

    blogs = ("medium.com", "blog", "zen.yandex.ru", "dzen.ru", "habr.com")
    if any(s in d for s in blogs):
        return "blog"

    media = (
        "ria.ru", "tass.ru", "interfax.ru", "kommersant.ru", "rg.ru", "rbc.ru",
        "newsvl.ru", "vl.ru", "vestiprim", "dv.kp.ru", "primamedia", "news.rambler.ru",
        "lenta.ru", "gazeta.ru", "mk.ru", "astv.ru", "eastrussia",
    )
    if any(s in d for s in media):
        return "media"

    return "other"


def normalize_domain_for_brand(domain: Optional[str]) -> str:
    """Lowercase, strip protocol/www and trailing slash."""
    d = extract_domain(domain)
    return d or ""

"""Tests for the URL/title helpers in scripts/scrape.py.

Network-touching code (fetch, RobotsCache._load) is intentionally not covered
here; correctness of the pure helpers is what would silently corrupt the
manifest if it broke.
"""

from __future__ import annotations

from scripts.scrape import (
    canonicalize_url,
    is_allowed_host,
    is_blocked_extension,
    is_blocked_path,
    is_news_or_case_study,
    url_to_slug,
)


# ---------- canonicalize_url ----------

def test_canonicalize_strips_fragment():
    assert canonicalize_url("https://www.fairwork.gov.au/leave#section") == \
        "https://www.fairwork.gov.au/leave"


def test_canonicalize_strips_tracking_params():
    src = "https://www.fairwork.gov.au/leave?utm_source=g&utm_medium=cpc&id=42"
    assert canonicalize_url(src) == "https://www.fairwork.gov.au/leave?id=42"


def test_canonicalize_lowercases_scheme_and_host():
    assert canonicalize_url("HTTPS://WWW.FAIRWORK.GOV.AU/Leave") == \
        "https://www.fairwork.gov.au/Leave"


def test_canonicalize_strips_trailing_slash():
    assert canonicalize_url("https://www.fairwork.gov.au/leave/") == \
        "https://www.fairwork.gov.au/leave"


def test_canonicalize_keeps_root_slash():
    assert canonicalize_url("https://www.fairwork.gov.au/") == \
        "https://www.fairwork.gov.au/"


def test_canonicalize_query_param_order_is_stable():
    a = canonicalize_url("https://www.fairwork.gov.au/x?b=2&a=1")
    b = canonicalize_url("https://www.fairwork.gov.au/x?a=1&b=2")
    assert a == b


def test_canonicalize_strips_default_ports():
    assert canonicalize_url("https://www.fairwork.gov.au:443/leave") == \
        "https://www.fairwork.gov.au/leave"
    assert canonicalize_url("http://www.fairwork.gov.au:80/leave") == \
        "http://www.fairwork.gov.au/leave"


# ---------- url_to_slug ----------

def test_url_to_slug_basic():
    assert url_to_slug("https://www.fairwork.gov.au/leave/parental-leave") == \
        "leave-parental-leave"


def test_url_to_slug_smallbusiness_prefix():
    slug = url_to_slug("https://smallbusiness.fairwork.gov.au/hiring/staff")
    assert slug == "sb-hiring-staff"


def test_url_to_slug_root():
    assert url_to_slug("https://www.fairwork.gov.au/") == "index"
    assert url_to_slug("https://smallbusiness.fairwork.gov.au/") == "sb-index"


def test_url_to_slug_lowercases():
    assert url_to_slug("https://www.fairwork.gov.au/Leave/Parental-Leave") == \
        "leave-parental-leave"


# ---------- domain / extension / path gates ----------

def test_is_allowed_host_accepts_both_subdomains():
    assert is_allowed_host("https://www.fairwork.gov.au/leave")
    assert is_allowed_host("https://smallbusiness.fairwork.gov.au/hiring")


def test_is_allowed_host_rejects_other_subdomains():
    assert not is_allowed_host("https://library.fairwork.gov.au/")
    assert not is_allowed_host("https://example.com/")


def test_is_blocked_extension_catches_pdf_and_image():
    assert is_blocked_extension("https://www.fairwork.gov.au/file.pdf")
    assert is_blocked_extension("https://www.fairwork.gov.au/img.jpg")
    assert is_blocked_extension("https://www.fairwork.gov.au/data.xlsx")


def test_is_blocked_extension_passes_html_pages():
    assert not is_blocked_extension("https://www.fairwork.gov.au/leave")
    assert not is_blocked_extension("https://www.fairwork.gov.au/leave/parental-leave")


def test_is_blocked_path_catches_news_paths():
    assert is_blocked_path("https://www.fairwork.gov.au/about/news/something")
    assert is_blocked_path("https://www.fairwork.gov.au/about/media-centre/release")


def test_is_blocked_path_passes_content_paths():
    assert not is_blocked_path("https://www.fairwork.gov.au/leave/parental-leave")
    assert not is_blocked_path("https://www.fairwork.gov.au/pay-and-wages")


# ---------- title filter ----------

def test_news_title_filter_catches_known_phrases():
    assert is_news_or_case_study("Latest News from Fair Work")
    assert is_news_or_case_study("Case Study: ABC Co.")
    assert is_news_or_case_study("Media Release: New ruling")
    assert is_news_or_case_study("Submission to inquiry")


def test_news_title_filter_passes_content_titles():
    assert not is_news_or_case_study("Annual leave entitlements")
    assert not is_news_or_case_study("Notice of termination and redundancy pay")
    assert not is_news_or_case_study("")

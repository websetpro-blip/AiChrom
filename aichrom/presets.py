# -*- coding: utf-8 -*-
"""Geolocation, language and timezone presets shared between UI and worker."""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict, Iterable, Tuple

DEFAULT_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.6533.120 Safari/537.36"
)


def _geo(lat: float, lon: float, accuracy: int = 50) -> Dict[str, float]:
    return {"latitude": lat, "longitude": lon, "accuracy": accuracy}


_PRESET_DEFINITIONS = [
    (
        "none",
        "Manual setup (no preset)",
        {
            "accept_language": None,
            "timezone": None,
            "lang_cli": None,
            "geo": None,
            "country": "",
            "tags": "",
            "user_agent": None,
        },
    ),
    (
        "kz_almaty",
        "Kazakhstan / Almaty (UTC+05)",
        {
            "accept_language": "ru-KZ,ru;q=0.9,kk-KZ;q=0.8,en-US;q=0.7",
            "timezone": "Asia/Almaty",
            "geo": _geo(43.2567, 76.9286),
            "country": "KZ",
            "tags": "kazakhstan almaty",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "kz_astana",
        "Kazakhstan / Astana (UTC+05)",
        {
            "accept_language": "ru-KZ,ru;q=0.9,kk-KZ;q=0.8,en-US;q=0.7",
            "timezone": "Asia/Almaty",
            "geo": _geo(51.1801, 71.4460),
            "country": "KZ",
            "tags": "kazakhstan astana",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "ru_moscow",
        "Russia / Moscow (UTC+03)",
        {
            "accept_language": "ru-RU,ru;q=0.9,en-US;q=0.6",
            "timezone": "Europe/Moscow",
            "geo": _geo(55.7558, 37.6176),
            "country": "RU",
            "tags": "russia moscow",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "ru_novosibirsk",
        "Russia / Novosibirsk (UTC+07)",
        {
            "accept_language": "ru-RU,ru;q=0.9,en-US;q=0.6",
            "timezone": "Asia/Novosibirsk",
            "geo": _geo(55.0084, 82.9357),
            "country": "RU",
            "tags": "russia novosibirsk",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "ru_vladivostok",
        "Russia / Vladivostok (UTC+10)",
        {
            "accept_language": "ru-RU,ru;q=0.9,en-US;q=0.6",
            "timezone": "Asia/Vladivostok",
            "geo": _geo(43.1155, 131.8855),
            "country": "RU",
            "tags": "russia vladivostok",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "by_minsk",
        "Belarus / Minsk (UTC+03)",
        {
            "accept_language": "ru-BY,ru;q=0.9,en-US;q=0.6",
            "timezone": "Europe/Minsk",
            "geo": _geo(53.9045, 27.5615),
            "country": "BY",
            "tags": "belarus minsk",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "ua_kyiv",
        "Ukraine / Kyiv (UTC+02/+03)",
        {
            "accept_language": "uk-UA,uk;q=0.9,ru;q=0.7,en-US;q=0.6",
            "timezone": "Europe/Kyiv",
            "geo": _geo(50.4501, 30.5234),
            "country": "UA",
            "tags": "ukraine kyiv",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "tr_istanbul",
        "Turkey / Istanbul (UTC+03)",
        {
            "accept_language": "tr-TR,tr;q=0.9,en-US;q=0.6",
            "timezone": "Europe/Istanbul",
            "geo": _geo(41.0082, 28.9784),
            "country": "TR",
            "tags": "turkey istanbul",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "pl_warsaw",
        "Poland / Warsaw (UTC+01)",
        {
            "accept_language": "pl-PL,pl;q=0.9,en-US;q=0.6",
            "timezone": "Europe/Warsaw",
            "geo": _geo(52.2297, 21.0122),
            "country": "PL",
            "tags": "poland warsaw",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "de_berlin",
        "Germany / Berlin (UTC+01)",
        {
            "accept_language": "de-DE,de;q=0.9,en-US;q=0.6",
            "timezone": "Europe/Berlin",
            "geo": _geo(52.5200, 13.4050),
            "country": "DE",
            "tags": "germany berlin",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "gb_london",
        "United Kingdom / London (UTC+00)",
        {
            "accept_language": "en-GB,en;q=0.9",
            "timezone": "Europe/London",
            "geo": _geo(51.5074, -0.1278),
            "country": "GB",
            "tags": "uk london",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "us_new_york",
        "USA / New York (UTC-05)",
        {
            "accept_language": "en-US,en;q=0.9",
            "timezone": "America/New_York",
            "geo": _geo(40.7128, -74.0060),
            "country": "US",
            "tags": "usa newyork",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "us_los_angeles",
        "USA / Los Angeles (UTC-08)",
        {
            "accept_language": "en-US,en;q=0.9",
            "timezone": "America/Los_Angeles",
            "geo": _geo(34.0522, -118.2437),
            "country": "US",
            "tags": "usa losangeles",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "ca_toronto",
        "Canada / Toronto (UTC-05)",
        {
            "accept_language": "en-CA,en;q=0.9,fr-CA;q=0.5",
            "timezone": "America/Toronto",
            "geo": _geo(43.6532, -79.3832),
            "country": "CA",
            "tags": "canada toronto",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "br_sao_paulo",
        "Brazil / Sao Paulo (UTC-03)",
        {
            "accept_language": "pt-BR,pt;q=0.9,en-US;q=0.6",
            "timezone": "America/Sao_Paulo",
            "geo": _geo(-23.5505, -46.6333),
            "country": "BR",
            "tags": "brazil saopaulo",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "in_delhi",
        "India / Delhi (UTC+05:30)",
        {
            "accept_language": "en-IN,en;q=0.9,hi;q=0.7",
            "timezone": "Asia/Kolkata",
            "geo": _geo(28.7041, 77.1025),
            "country": "IN",
            "tags": "india delhi",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
    (
        "sg_singapore",
        "Singapore (UTC+08)",
        {
            "accept_language": "en-SG,en;q=0.9,zh-CN;q=0.6",
            "timezone": "Asia/Singapore",
            "geo": _geo(1.3521, 103.8198),
            "country": "SG",
            "tags": "singapore",
            "user_agent": DEFAULT_CHROME_UA,
        },
    ),
]

GEO_PRESETS: Dict[str, Dict[str, object]] = OrderedDict()
for key, label, details in _PRESET_DEFINITIONS:
    data = dict(details)
    data.setdefault("lang_cli", None)
    data["label"] = label
    GEO_PRESETS[key] = data

PRESET_KEYS: Tuple[str, ...] = tuple(GEO_PRESETS.keys())
PRESET_LABEL_BY_KEY: Dict[str, str] = {key: data["label"] for key, data in GEO_PRESETS.items()}
PRESET_LABEL_LIST: Tuple[str, ...] = tuple(PRESET_LABEL_BY_KEY[key] for key in PRESET_KEYS)
PRESET_KEY_BY_LABEL: Dict[str, str] = {label: key for key, label in PRESET_LABEL_BY_KEY.items()}


def labels() -> Iterable[str]:
    """Return preset labels in stable order."""

    return PRESET_LABEL_LIST


def label_by_key(key: str) -> str:
    return PRESET_LABEL_BY_KEY.get(key, PRESET_LABEL_BY_KEY["none"])


def key_by_label(label: str) -> str:
    return PRESET_KEY_BY_LABEL.get(label, "none")


__all__ = [
    "DEFAULT_CHROME_UA",
    "GEO_PRESETS",
    "PRESET_KEYS",
    "PRESET_LABEL_BY_KEY",
    "PRESET_LABEL_LIST",
    "PRESET_KEY_BY_LABEL",
    "labels",
    "label_by_key",
    "key_by_label",
]

"""Blizzard's WoW Profile API: client-credentials token, requests and mapping.

Blizzard refreshes a character's profile when the player logs out, so this is
fresher than a third-party crawl, but it is still not live in-game telemetry.
"""

import hashlib
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from .fields import _display, _mapping, _number, _sequence, _text, derived

TOKEN_URL = "https://oauth.battle.net/token"
USER_AGENT = "FiestaBoard-WoW/1.0 (+https://fiestaboard.app)"
CURRENT_SEASON_EXPANSION = 505  # Pseudo-expansion listing this season's raids.
DIFFICULTIES = (("MYTHIC", "M"), ("HEROIC", "H"), ("NORMAL", "N"))
ARMORY_LOCALES = {"us": "en-us", "eu": "en-gb", "kr": "ko-kr", "tw": "zh-tw"}

# en_US spec names. Shared names (Frost, Holy, Protection, Restoration) have
# the same role for every class, so the name alone is unambiguous.
SPEC_ROLES = {
    **dict.fromkeys(("Blood", "Vengeance", "Guardian", "Brewmaster", "Protection"), "TANK"),
    **dict.fromkeys(("Restoration", "Preservation", "Mistweaver", "Holy", "Discipline"), "HEALING"),
    **dict.fromkeys((
        "Frost", "Unholy", "Havoc", "Devourer", "Balance", "Feral", "Devastation",
        "Augmentation", "Beast Mastery", "Marksmanship", "Survival", "Arcane", "Fire",
        "Windwalker", "Retribution", "Shadow", "Assassination", "Outlaw", "Subtlety",
        "Elemental", "Enhancement", "Affliction", "Demonology", "Destruction", "Arms",
        "Fury"), "DPS"),
}


class BlizzardError(Exception):
    """A refresh failure whose message is safe to show the user."""


class RateLimited(BlizzardError):
    def __init__(self, delay: int):
        super().__init__("Blizzard rate limit; waiting before retrying.")
        self.delay = delay


class NotFound(BlizzardError):
    pass


def realm_slug(realm: str) -> str:
    """Slug for Latin realm names; non-Latin realms must be entered as a slug."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", realm) if not unicodedata.combining(c))
    return re.sub(r"\s+", "-", plain.strip().lower().replace("'", "").replace("\u2019", ""))


def _retry_after(response) -> int:
    try:
        return max(1, int(response.headers.get("Retry-After", "60")))
    except (ValueError, TypeError):
        return 60


class BlizzardClient:
    """Holds one cached access token; owned by a single plugin instance."""

    def __init__(self):
        self.clear()

    def clear(self) -> None:
        self._token: str | None = None
        self._token_key: tuple | None = None
        self._expires_at = 0.0

    def __repr__(self) -> str:
        return "BlizzardClient()"

    def _access_token(self, client_id: str, secret: str) -> str:
        # Hash the secret so it never sits in a cache key or a traceback.
        key = (client_id, hashlib.sha256(secret.encode()).hexdigest())
        if self._token and key == self._token_key and time.monotonic() < self._expires_at:
            return self._token
        response = requests.post(TOKEN_URL, auth=(client_id, secret),
                                 data={"grant_type": "client_credentials"},
                                 headers={"User-Agent": USER_AGENT}, timeout=3)
        if response.status_code == 429:
            raise RateLimited(_retry_after(response))
        if response.status_code in (400, 401, 403):
            raise BlizzardError("Blizzard rejected the client ID or secret. Check your Battle.net API client.")
        response.raise_for_status()
        payload = _mapping(response.json())
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("Missing access token")
        lifetime = _number(payload.get("expires_in")) or 0
        self._token, self._token_key = token, key
        self._expires_at = time.monotonic() + max(0, lifetime - 60)
        return token

    def get(self, config: dict, path: str) -> dict:
        region = config.get("region", "eu")
        client_id, secret = config["client_id"], config["client_secret"]
        for attempt in (0, 1):
            response = requests.get(
                f"https://{region}.api.blizzard.com{path}",
                headers={"Authorization": f"Bearer {self._access_token(client_id, secret)}",
                         "Battlenet-Namespace": f"profile-{region}", "User-Agent": USER_AGENT},
                params={"locale": "en_US"}, timeout=3)
            if response.status_code == 401 and attempt == 0:
                self.clear()  # Revoked or expired early; fetch one new token.
                continue
            break
        if response.status_code == 429:
            raise RateLimited(_retry_after(response))
        if response.status_code == 401:
            raise BlizzardError("Blizzard rejected the client ID or secret. Check your Battle.net API client.")
        if response.status_code == 403:
            raise BlizzardError("Blizzard refused access. Check the region matches the realm.")
        if response.status_code == 404:
            raise NotFound("Character not found. Check region, the realm slug from your Armory URL, and spelling.")
        response.raise_for_status()
        return _mapping(response.json())

    def optional(self, config: dict, path: str) -> dict:
        """A sub-resource whose absence must not hide the character summary."""
        try:
            return self.get(config, path)
        except RateLimited:
            raise
        except (BlizzardError, requests.RequestException, ValueError):
            return {}

    def fetch(self, config: dict) -> tuple[dict, dict, dict, dict]:
        name = config["character"].strip().lower()
        base = "/profile/wow/character/" + "/".join(
            quote(v, safe="") for v in (realm_slug(config["realm"]), name))
        summary = self.get(config, base)
        return (summary, self.optional(config, base + "/mythic-keystone-profile"),
                self.optional(config, base + "/encounters/raids"),
                self.optional(config, base + "/character-media"))


def _named(value) -> str:
    return _text(value.get("name")) if isinstance(value, dict) else ""


def _safe(parse, value, default):
    try:
        return parse(value)
    except (ValueError, TypeError, KeyError, AttributeError):
        return default


def _runs(mkp: dict) -> list:
    runs = []
    for item in _sequence(_mapping(mkp.get("current_period")).get("best_runs")):
        run = _mapping(item)
        level = _number(run.get("keystone_level"))
        if level is None:
            continue
        timed = run.get("is_completed_within_time")
        runs.append({"dungeon": _named(run.get("dungeon")), "short_name": "", "level": level,
                     "timed": timed if isinstance(timed, bool) else None,
                     "score": _number(_mapping(run.get("mythic_rating")).get("rating"))})
    return runs


def _raid(instance: dict) -> dict:
    name = _named(instance.get("instance"))
    counts, totals = {}, []
    for item in _sequence(instance.get("modes")):
        m = _mapping(item)
        kind = _mapping(m.get("difficulty")).get("type")
        if kind not in ("NORMAL", "HEROIC", "MYTHIC"):
            continue  # LFR wings open gradually; LEGACY_* belong to old raids.
        progress = _mapping(m.get("progress"))
        counts[kind] = _number(progress.get("completed_count")) or 0
        total = _number(progress.get("total_count"))
        if total is not None:
            totals.append(total)
    total = max(totals, default=None)
    summary = "NO DATA"
    if total is not None:
        summary = f"0/{total:g} N"
        for kind, letter in DIFFICULTIES:
            if counts.get(kind):
                summary = f"{counts[kind]:g}/{total:g} {letter}"
                break
    return {"slug": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), "name": name,
            "summary": summary, "total_bosses": total,
            **{f"{k.lower()}_bosses_killed": counts.get(k, 0) for k in ("NORMAL", "HEROIC", "MYTHIC")}}


def _raids(data: dict) -> list:
    expansions = [_mapping(e) for e in _sequence(data.get("expansions"))]
    def eid(e):
        value = _mapping(e.get("expansion")).get("id")
        return value if isinstance(value, int) and not isinstance(value, bool) else -1
    current = [e for e in expansions if eid(e) == CURRENT_SEASON_EXPANSION and _sequence(e.get("instances"))]
    real = sorted((e for e in expansions if eid(e) not in (-1, CURRENT_SEASON_EXPANSION)), key=eid)
    chosen = current[0] if current else (real[-1] if real else {})
    return [_raid(_mapping(i)) for i in _sequence(chosen.get("instances"))]


def _avatar_url(media: dict) -> str | None:
    assets = {a.get("key"): a.get("value") for a in _sequence(media.get("assets")) if isinstance(a, dict)}
    return assets.get("avatar") or assets.get("inset")


def build_profile(summary, mkp, raids, media, config: dict) -> tuple[dict, str | None]:
    """Map Blizzard responses to the plugin's provider-neutral variables."""
    p = _mapping(summary)
    if not (isinstance(p.get("name"), str) and p["name"] and _named(p.get("realm"))
            and _named(p.get("character_class"))):
        raise ValueError("Missing character identity")
    now = datetime.now(timezone.utc)
    mkp = _mapping(mkp)
    seasons = [s.get("id") for s in _safe(_sequence, mkp.get("seasons"), []) if isinstance(s, dict)]
    season = max((s for s in seasons if isinstance(s, int) and not isinstance(s, bool)), default=None)
    rating = _number(_safe(lambda m: _mapping(m.get("current_mythic_rating")).get("rating"), mkp, None))
    login = _number(p.get("last_login_timestamp"))
    updated = ""
    if login is not None:
        try:
            updated = datetime.fromtimestamp(login / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except (ValueError, OverflowError, OSError):
            pass  # Out-of-range timestamp: freshness becomes UNKNOWN.
    region = config.get("region", "eu")
    spec = _named(p.get("active_spec"))
    ilvl = _number(p.get("equipped_item_level"))
    url = "https://worldofwarcraft.blizzard.com/{}/character/{}/{}/{}".format(
        ARMORY_LOCALES.get(region, "en-us"), region,
        quote(realm_slug(config["realm"]), safe=""), quote(config["character"].strip().lower(), safe=""))
    data = {
        "name": _text(p["name"]), "realm": _named(p["realm"]), "region": region.upper(),
        "class": _named(p["character_class"]), "spec": spec, "role": SPEC_ROLES.get(spec, ""),
        "race": _named(p.get("race")), "faction": _named(p.get("faction")),
        "guild": _named(p.get("guild")), "achievement_points": _number(p.get("achievement_points")),
        "item_level": ilvl, "item_level_display": _display(ilvl),
        "season": "" if season is None else str(season), "mythic_score": rating,
        "mythic_score_display": _display(rating), "healer_score": None,
        "source": "Blizzard", "source_short": "BNET", "profile_url": url,
        **derived(_safe(_runs, mkp, []), _safe(_raids, _mapping(raids), []), updated, now),
    }
    return data, _safe(_avatar_url, _mapping(media), None)

"""World of Warcraft Retail profiles from Raider.IO, or Blizzard's Profile API."""

import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from src.plugins.base import PluginBase, PluginResult
from .avatar import DECODE_ERRORS, avatar_canvas, download_avatar, image_decoder_available, trusted_avatar_url
from .blizzard import BlizzardClient, BlizzardError, RateLimited, build_profile
from .fields import _display, _mapping, _number, _sequence, _text, derived

PROFILE_URL = "https://raider.io/api/v1/characters/profile"
FIELDS = ",".join((
    "gear", "guild", "mythic_plus_scores_by_season:current",
    "mythic_plus_weekly_highest_level_runs", "raid_progression:current-tier",
))


class WoWPlugin(PluginBase):
    """One configurable Retail character; AI art remains a separate plugin."""

    def __init__(self, manifest: dict[str, Any]):
        self._fetch_lock = threading.RLock()
        super().__init__(manifest)
        self._last_good: dict | None = None
        self._retry_at = 0.0
        self._avatar_bytes: bytes | None = None
        self._avatar_key: tuple | None = None
        self._avatar_fetched_at = 0.0
        self._blizzard = BlizzardClient()

    @property
    def plugin_id(self) -> str:
        return "wow"

    @PluginBase.config.setter
    def config(self, value: dict[str, Any]) -> None:
        # The base setter assigns settings BEFORE invoking on_config_change.
        # Lock the whole setter against get_data, including its cache write.
        with self._fetch_lock:
            PluginBase.config.fset(self, value)

    def get_data(self, board=None) -> PluginResult:
        with self._fetch_lock:
            return super().get_data(board=board)

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if config.get("region", "eu") not in ("eu", "us", "kr", "tw"):
            errors.append("Region must be eu, us, kr, or tw.")
        for field in ("realm", "character"):
            value = config.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"A {field} is required.")
            elif len(value) > 100 or any(ord(c) < 32 for c in value):
                errors.append(f"Invalid {field}.")
        for field in ("avatar_width", "avatar_height"):
            value = config.get(field, 64)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 128:
                errors.append(f"{field} must be a whole number from 1 to 128.")
        source = config.get("data_source", "auto")
        if source not in ("auto", "raiderio", "blizzard"):
            errors.append("Data source must be auto, raiderio, or blizzard.")
        if source == "raiderio":
            return errors  # Credential fields are hidden and unused in this mode.
        filled = 0
        for field, label in (("client_id", "client ID"), ("client_secret", "client secret")):
            value = config.get(field, "")
            if value in ("", None):
                continue
            filled += 1
            # "***" is the masked placeholder; it must never reach Blizzard.
            if (not isinstance(value, str) or len(value) > 200 or value == "***"
                    or any(ord(c) < 33 for c in value)):
                errors.append(f"Invalid Battle.net {label}.")
        if filled == 1 or (source == "blizzard" and filled == 0):
            errors.append("Both a Battle.net client ID and client secret are required.")
        return errors

    @staticmethod
    def _uses_blizzard(config: dict) -> bool:
        return config.get("data_source", "auto") != "raiderio" and bool(
            config.get("client_id") and config.get("client_secret"))

    def on_config_change(self, old_config: dict, new_config: dict) -> None:
        # Serialize with fetches so a previous character cannot repopulate the
        # fallback after a settings change. Preserve the provider's rate backoff.
        with self._fetch_lock:
            self._last_good = None
            if any(old_config.get(k) != new_config.get(k) for k in ("region", "realm", "character")):
                self._avatar_bytes = None
                self._avatar_key = None
                self._avatar_fetched_at = 0.0
            if any(old_config.get(k) != new_config.get(k) for k in ("client_id", "client_secret")):
                self._blizzard.clear()
            if self._uses_blizzard(old_config) != self._uses_blizzard(new_config):
                self._retry_at = 0.0  # One provider's backoff must not block the other.

    def fetch_data(self) -> PluginResult:
        with self._fetch_lock:
            config = dict(self.config)
            errors = self.validate_config(config)
            if errors:
                return PluginResult(available=False, error=" ".join(errors))
            if self._uses_blizzard(config):
                return self._fetch_blizzard(config)
            if time.monotonic() < self._retry_at:
                return self._failure("Raider.IO rate limit; waiting before retrying.")
            try:
                response = requests.get(
                    PROFILE_URL,
                    params={"region": config.get("region", "eu"),
                            "realm": config["realm"].strip(),
                            "name": config["character"].strip(), "fields": FIELDS},
                    headers={"User-Agent": "FiestaBoard-WoW/1.0 (+https://fiestaboard.app)"},
                    timeout=3,
                )
                if response.status_code == 429:
                    try:
                        delay = max(1, int(response.headers.get("Retry-After", "60")))
                    except (ValueError, TypeError):
                        delay = 60
                    self._retry_at = time.monotonic() + delay
                    return self._failure("Raider.IO rate limit; waiting before retrying.")
                if response.status_code in (400, 404):
                    return self._failure("Character not found. Check Retail region, realm, and exact character spelling.")
                response.raise_for_status()
                payload = response.json()
                data = self._profile(payload, config)
            except requests.RequestException:
                return self._failure("Raider.IO is unavailable or timed out.")
            except (ValueError, TypeError, KeyError):
                return self._failure("Raider.IO returned an invalid character profile.")
            data.update(self._avatar(payload.get("thumbnail_url"), payload.get("last_crawled_at"), config))
            self._last_good = data
            return self._result(data)

    def _fetch_blizzard(self, config: dict) -> PluginResult:
        if time.monotonic() < self._retry_at:
            return self._failure("Blizzard rate limit; waiting before retrying.")
        try:
            data, avatar_url = build_profile(*self._blizzard.fetch(config), config)
        except RateLimited as exc:
            self._retry_at = time.monotonic() + exc.delay
            return self._failure(str(exc))
        except BlizzardError as exc:
            return self._failure(str(exc))
        except requests.RequestException:
            return self._failure("Blizzard is unavailable or timed out.")
        except (ValueError, TypeError, KeyError):
            return self._failure("Blizzard returned an invalid character profile.")
        data.update(self._avatar(avatar_url, data["source_updated_at"], config))
        self._last_good = data
        return self._result(data)

    def _avatar(self, url, version, config: dict) -> dict:
        key = (url, version)
        width, height = config.get("avatar_width", 64), config.get("avatar_height", 64)
        status = "OK"
        canvas = None
        try:
            if not image_decoder_available():
                raise ValueError("Avatar decoder unavailable")
            if not trusted_avatar_url(url):
                raise ValueError("Avatar URL unavailable")
            if self._avatar_bytes is None or key != self._avatar_key or time.monotonic() - self._avatar_fetched_at >= 21600:
                image = download_avatar(url)
                canvas = avatar_canvas(image, width, height)
                # Commit cache only after both download and decode succeed.
                self._avatar_bytes, self._avatar_key = image, key
                self._avatar_fetched_at = time.monotonic()
            else:
                canvas = avatar_canvas(self._avatar_bytes, width, height)
        except (requests.RequestException, *DECODE_ERRORS):
            status = "UNAVAILABLE"
            if self._avatar_bytes is not None:
                canvas = avatar_canvas(self._avatar_bytes, width, height)
                status = "STALE"
        return {"avatar_canvas": canvas, "avatar_status": status,
                "avatar_url": self._avatar_key[0] if canvas is not None else ""}

    def _profile(self, payload: Any, config: dict) -> dict:
        p = _mapping(payload)
        if not all(isinstance(p.get(k), str) and p[k] for k in ("name", "realm", "class")):
            raise ValueError("Missing character identity")
        now = datetime.now(timezone.utc)
        gear = _mapping(p.get("gear"))
        guild = _mapping(p.get("guild"))
        seasons = _sequence(p.get("mythic_plus_scores_by_season"))
        season = _mapping(seasons[0]) if seasons else {}
        scores = _mapping(season.get("scores"))
        runs = []
        for item in _sequence(p.get("mythic_plus_weekly_highest_level_runs")):
            run = _mapping(item)
            level = _number(run.get("mythic_level"))
            if level is None:
                continue
            upgrades = _number(run.get("num_keystone_upgrades"))
            runs.append({"dungeon": _text(run.get("dungeon")),
                         "short_name": _text(run.get("short_name")), "level": level,
                         "timed": None if upgrades is None else upgrades > 0,
                         "score": _number(run.get("score"))})
        raids = []
        for slug, value in _mapping(p.get("raid_progression")).items():
            raid = _mapping(value)
            raids.append({"slug": slug, "name": slug.replace("-", " ").title(),
                          "summary": _text(raid.get("summary")) or "NO DATA",
                          **{key: _number(raid.get(key)) for key in (
                              "total_bosses", "normal_bosses_killed",
                              "heroic_bosses_killed", "mythic_bosses_killed")}})
        region = config.get("region", "eu")
        # Build a trusted source URL, rather than rendering an arbitrary URL
        # returned by an upstream service.
        url = "https://raider.io/characters/" + "/".join(
            quote(v, safe="") for v in (region, config["realm"].strip(), p["name"]))
        ilvl, score = _number(gear.get("item_level_equipped")), _number(scores.get("all"))
        return {
            "name": _text(p["name"]), "realm": _text(p["realm"]), "region": region.upper(),
            "class": _text(p["class"]), "spec": _text(p.get("active_spec_name")),
            "role": _text(p.get("active_spec_role")), "race": _text(p.get("race")),
            "faction": _text(p.get("faction")), "guild": _text(guild.get("name")),
            "achievement_points": _number(p.get("achievement_points")),
            "item_level": ilvl, "item_level_display": _display(ilvl),
            "season": _text(season.get("season")), "mythic_score": score,
            "mythic_score_display": _display(score), "healer_score": _number(scores.get("healer")),
            "source": "Raider.IO", "source_short": "RIO", "profile_url": url,
            **derived(runs, raids, _text(p.get("last_crawled_at")), now),
        }

    def _result(self, data: dict, error: str | None = None) -> PluginResult:
        board = self.board
        rows, cols = (board.rows, board.cols) if board else (6, 22)
        lines = [data["name"], f"ILVL {data['item_level_display']}",
                 f"M+ {data['mythic_score_display']}",
                 f"WEEK {data['weekly_key_display']}", data["raid_progress"],
                 "STALE" if data["stale"] else f"{data.get('source_short', 'RIO')} {data['source_updated_date']}"]
        return PluginResult(available=True, data=data, error=error,
                            formatted_lines=[line[:cols] for line in lines[:rows]])

    def _failure(self, message: str) -> PluginResult:
        if self._last_good is None:
            return PluginResult(available=False, error=message)
        return self._result({**self._last_good, "stale": True, "status": "STALE",
                             "avatar_status": "STALE" if self._last_good.get("avatar_canvas") else "UNAVAILABLE"}, message)

    def get_formatted_display(self) -> list[str] | None:
        result = self.get_data()
        return result.formatted_lines if result.available else None

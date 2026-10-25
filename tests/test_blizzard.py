"""Blizzard Profile API source with synthetic responses shaped like the real API; no live network."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from wow import WoWPlugin
from .conftest import response

BASE = "https://eu.api.blizzard.com/profile/wow/character/example-realm/example"
TOKEN_URL = "https://oauth.battle.net/token"
AVATAR = "https://render.worldofwarcraft.com/eu/character/example/1/2-avatar.jpg"
CREDS = {"client_id": "id-123", "client_secret": "secret-456"}


@pytest.fixture
def bnet():
    p = WoWPlugin({"id": "wow", "name": "World of Warcraft", "version": "1.2.0"})
    p.config = {"region": "eu", "realm": "Example Realm", "character": "Example", **CREDS}
    return p


def summary():
    return {
        "name": "Example", "realm": {"name": "Example Realm", "slug": "example-realm"},
        "character_class": {"name": "Druid"}, "active_spec": {"name": "Restoration"},
        "race": {"name": "Night Elf"}, "faction": {"type": "ALLIANCE", "name": "Alliance"},
        "guild": {"name": "Example Guild"}, "achievement_points": 12345,
        "equipped_item_level": 281, "average_item_level": 283,
        "last_login_timestamp": 1792663200000,  # 2026-10-22T10:00:00Z
    }


def keystone():
    return {
        "current_period": {"period": {"id": 1040}, "best_runs": [
            {"keystone_level": 12, "is_completed_within_time": False,
             "dungeon": {"name": "Example Dungeon", "id": 1}, "mythic_rating": {"rating": 210.5}},
            {"keystone_level": 11, "is_completed_within_time": True,
             "dungeon": {"name": "Example Dungeon", "id": 1}, "mythic_rating": {"rating": 220.0}},
            {"keystone_level": 10, "is_completed_within_time": True,
             "dungeon": {"name": "Another Dungeon", "id": 2}, "mythic_rating": {"rating": 200.0}},
        ]},
        "seasons": [{"id": 6}, {"id": 15}, {"id": 13}, {"id": "bad"}],
        "current_mythic_rating": {"rating": 2789.4, "color": {}},
    }


def mode(kind, done, total):
    return {"difficulty": {"type": kind, "name": kind.title()}, "status": {"type": "IN_PROGRESS"},
            "progress": {"completed_count": done, "total_count": total, "encounters": []}}


def raids():
    current = [
        {"instance": {"name": "The Voidspire", "id": 1}, "modes": [
            mode("LFR", 2, 4), mode("NORMAL", 6, 6), mode("HEROIC", 4, 6)]},
        {"instance": {"name": "The Dreamrift", "id": 2}, "modes": [mode("NORMAL", 1, 1)]},
        {"instance": {"name": "March on Quel'Danas", "id": 3}, "modes": [
            mode("NORMAL", 2, 2), mode("HEROIC", 2, 2), mode("MYTHIC", 1, 2)]},
    ]
    return {"expansions": [
        {"expansion": {"name": "Classic", "id": 68}, "instances": [
            {"instance": {"name": "Molten Core", "id": 9}, "modes": [mode("LEGACY_40_MAN", 10, 10)]}]},
        {"expansion": {"name": "Current Season", "id": 505}, "instances": current},
        {"expansion": {"name": "Midnight", "id": 516}, "instances": current},
    ]}


def media():
    return {"assets": [{"key": "inset", "value": AVATAR.replace("avatar", "inset")},
                       {"key": "avatar", "value": AVATAR}, {"key": "main-raw", "value": AVATAR}]}


def token(expires=86399):
    return response({"access_token": "tok-1", "token_type": "bearer", "expires_in": expires})


class FakeBlizzard:
    """Routes requests.get by URL; records every call."""

    def __init__(self, **overrides):
        self.routes = {"": summary(), "/mythic-keystone-profile": keystone(),
                       "/encounters/raids": raids(), "/character-media": media()}
        self.routes.update(overrides)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.startswith("https://render.worldofwarcraft.com/"):
            raise requests.Timeout  # Portrait unavailable unless a test supplies one.
        if not url.startswith(BASE):
            raise AssertionError(f"unexpected URL {url}")
        reply = self.routes[url[len(BASE):]]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, int):
            return response({}, reply)
        return reply if hasattr(reply, "status_code") else response(reply)


def run(plugin, fake=None, post=None):
    fake = fake or FakeBlizzard()
    with patch("requests.post", side_effect=post or [token()]) as p, patch("requests.get", side_effect=fake):
        result = plugin.fetch_data()
    return result, fake, p


# --- Configuration --------------------------------------------------------

def test_data_source_enum_and_blizzard_needs_both_credentials(bnet):
    base = {"region": "eu", "realm": "r", "character": "c"}
    assert bnet.validate_config({**base, "data_source": "nope"})
    assert bnet.validate_config({**base, "data_source": "blizzard"})
    assert bnet.validate_config({**base, "data_source": "blizzard", "client_id": "x"})
    assert not bnet.validate_config({**base, "data_source": "blizzard", **CREDS})
    assert not bnet.validate_config({**base, "data_source": "auto"})
    assert not bnet.validate_config({**base, "data_source": "raiderio", **CREDS})
    # Half a credential pair is a paste error, never a silent Raider.IO fallback.
    for mode_ in ("auto", "raiderio"):
        assert bnet.validate_config({**base, "data_source": mode_, "client_id": "x"})
        assert bnet.validate_config({**base, "data_source": mode_, "client_secret": "x"})
    assert not bnet.validate_config({**base, "client_id": "", "client_secret": ""})


@pytest.mark.parametrize("value", ["***", "x" * 201, "a\nb", 5])
def test_malformed_or_masked_credentials_rejected_before_network(bnet, value):
    bnet.config = {**bnet.config, "client_secret": value}
    assert bnet.validate_config(bnet.config)
    with patch("requests.post", side_effect=AssertionError("network")), \
         patch("requests.get", side_effect=AssertionError("network")):
        assert not bnet.fetch_data().available


def test_auto_without_credentials_still_uses_raiderio(bnet, profile):
    bnet.config = {"region": "eu", "realm": "example-realm", "character": "Example"}
    with patch("requests.post", side_effect=AssertionError("token request")), \
         patch("requests.get", return_value=response(profile)) as get:
        result = bnet.fetch_data()
    assert result.available and result.data["source"] == "Raider.IO"
    assert result.data["source_short"] == "RIO"
    assert get.call_args.args[0] == "https://raider.io/api/v1/characters/profile"


def test_explicit_raiderio_ignores_credentials(bnet, profile):
    bnet.config = {**bnet.config, "data_source": "raiderio", "realm": "example-realm"}
    with patch("requests.post", side_effect=AssertionError("token request")), \
         patch("requests.get", return_value=response(profile)):
        assert bnet.fetch_data().data["source"] == "Raider.IO"


# --- Requests -------------------------------------------------------------

def test_token_then_profile_calls_use_bearer_namespace_and_lowercase_slugs(bnet):
    bnet.config = {**bnet.config, "realm": " Example Realm ", "character": "Example"}
    result, fake, post = run(bnet)
    assert result.available
    assert post.call_args.args[0] == TOKEN_URL
    assert post.call_args.kwargs["auth"] == ("id-123", "secret-456")
    assert post.call_args.kwargs["data"] == {"grant_type": "client_credentials"}
    assert post.call_args.kwargs["timeout"] <= 4
    api_calls = [(u, k) for u, k in fake.calls if u.startswith(BASE)]
    assert {url[len(BASE):] for url, _ in api_calls} == set(FakeBlizzard().routes)
    for _, kwargs in api_calls:
        assert kwargs["headers"]["Authorization"] == "Bearer tok-1"
        assert kwargs["headers"]["Battlenet-Namespace"] == "profile-eu"
        assert "FiestaBoard-WoW" in kwargs["headers"]["User-Agent"]
        assert kwargs["params"]["locale"] == "en_US"
        assert kwargs["timeout"] <= 4


@pytest.mark.parametrize("realm,slug", [("Azjol-Nerub", "azjol-nerub"), ("Mal'Ganis", "malganis"),
                                         ("Area 52", "area-52"), ("argent-dawn", "argent-dawn"),
                                         ("Confrérie du Thorium", "confrerie-du-thorium"),
                                         ("Festung der Stürme", "festung-der-sturme"),
                                         ("Pozzo dell’Eternità", "pozzo-delleternita"),
                                         ("La Croisade écarlate", "la-croisade-ecarlate")])
def test_realm_slug(realm, slug):
    from wow.blizzard import realm_slug
    assert realm_slug(realm) == slug


def test_accented_name_is_lowercased_and_url_encoded(bnet):
    bnet.config = {**bnet.config, "character": "Éxample"}
    seen = []
    def get(url, **kwargs):
        seen.append(url)
        return response(summary()) if url.endswith("/%C3%A9xample") else response({}, 404)
    with patch("requests.post", side_effect=[token()]), patch("requests.get", side_effect=get):
        assert bnet.fetch_data().available
    assert seen[0] == "https://eu.api.blizzard.com/profile/wow/character/example-realm/%C3%A9xample"


# --- Mapping --------------------------------------------------------------

def test_profile_maps_to_existing_variable_contract(bnet):
    d = run(bnet)[0].data
    assert (d["name"], d["realm"], d["region"], d["class"], d["spec"]) == ("Example", "Example Realm", "EU", "Druid", "Restoration")
    assert (d["race"], d["faction"], d["guild"]) == ("Night Elf", "Alliance", "Example Guild")
    assert d["role"] == "HEALING"
    assert d["achievement_points"] == 12345
    assert d["item_level"] == 281 and d["item_level_display"] == "281"
    assert d["mythic_score"] == 2789.4 and d["mythic_score_display"] == "2789"
    assert d["healer_score"] is None
    assert d["season"] == "15"
    assert d["source"] == "Blizzard" and d["source_short"] == "BNET"
    assert d["source_updated_at"] == "2026-10-22T10:00:00.000Z"
    assert d["source_updated_date"] == "2026-10-22"
    assert d["profile_url"] == "https://worldofwarcraft.blizzard.com/en-gb/character/eu/example-realm/example"
    assert d["fetched_at"] != d["source_updated_at"]
    assert d["stale"] is False


def test_weekly_runs_keep_duplicate_dungeon_and_separate_timed_key(bnet):
    d = run(bnet)[0].data
    assert [(r["dungeon"], r["level"], r["timed"]) for r in d["weekly_runs"]] == [
        ("Example Dungeon", 12, False), ("Example Dungeon", 11, True), ("Another Dungeon", 10, True)]
    assert d["weekly_runs"][0]["score"] == 210.5
    assert d["weekly_highest_key"] == 12 and d["weekly_highest_timed_key"] == 11
    assert d["weekly_key_display"] == "+12"


def test_current_season_raids_all_listed_with_highest_difficulty_summary(bnet):
    d = run(bnet)[0].data
    assert [r["name"] for r in d["raids"]] == ["The Voidspire", "The Dreamrift", "March on Quel'Danas"]
    void = d["raids"][0]
    assert void["slug"] == "the-voidspire"
    assert void["total_bosses"] == 6  # LFR's partial wing count is ignored.
    assert (void["normal_bosses_killed"], void["heroic_bosses_killed"], void["mythic_bosses_killed"]) == (6, 4, 0)
    assert d["raid_progress"] == "4/6 H | 1/1 N | 1/2 M"


def test_raids_fall_back_to_newest_real_expansion_without_current_season(bnet):
    data = raids()
    data["expansions"] = [e for e in data["expansions"] if e["expansion"]["id"] != 505]
    d = run(bnet, FakeBlizzard(**{"/encounters/raids": data}))[0].data
    assert len(d["raids"]) == 3 and d["raids"][2]["summary"] == "1/2 M"


def test_empty_current_season_falls_through_to_newest_expansion(bnet):
    data = raids()
    data["expansions"][1]["instances"] = []
    d = run(bnet, FakeBlizzard(**{"/encounters/raids": data}))[0].data
    assert d["raid_progress"] == "4/6 H | 1/1 N | 1/2 M"


def test_raid_without_totals_is_no_data_and_missing_kills_are_zero(bnet):
    no_total = {"difficulty": {"type": "NORMAL"}, "progress": {"completed_count": 1}}
    no_kills = {"difficulty": {"type": "HEROIC"}, "progress": {"total_count": 3}}
    data = {"expansions": [{"expansion": {"id": 505}, "instances": [
        {"instance": {"name": "Odd Raid"}, "modes": [no_total]},
        {"instance": {"name": "Fresh Raid"}, "modes": [no_kills]}]}]}
    d = run(bnet, FakeBlizzard(**{"/encounters/raids": data}))[0].data
    assert [r["summary"] for r in d["raids"]] == ["NO DATA", "0/3 N"]
    assert d["raids"][1]["heroic_bosses_killed"] == 0


def test_raid_without_kills_reports_zero_normal(bnet):
    data = {"expansions": [{"expansion": {"id": 505, "name": "Current Season"}, "instances": [
        {"instance": {"name": "New Raid", "id": 7}, "modes": [mode("NORMAL", 0, 8)]}]}]}
    d = run(bnet, FakeBlizzard(**{"/encounters/raids": data}))[0].data
    assert d["raid_progress"] == "0/8 N"


def test_no_rating_this_season_is_unknown_not_zero(bnet):
    k = keystone()
    k.pop("current_mythic_rating")
    k["current_period"]["best_runs"] = []
    d = run(bnet, FakeBlizzard(**{"/mythic-keystone-profile": k}))[0].data
    assert d["mythic_score"] is None and d["mythic_score_display"] == "--"
    assert d["weekly_key_display"] == "--"


@pytest.mark.parametrize("failure", [404, requests.Timeout(), ["not", "an", "object"]])
def test_optional_resources_failing_leave_fields_empty_but_profile_available(bnet, failure):
    fake = FakeBlizzard(**{"/mythic-keystone-profile": failure, "/encounters/raids": failure,
                           "/character-media": failure})
    d = run(bnet, fake)[0].data
    assert d["name"] == "Example" and d["item_level"] == 281
    assert d["mythic_score"] is None and d["season"] == "" and d["weekly_runs"] == []
    assert d["raids"] == [] and d["raid_progress"] == "NO DATA"
    assert d["avatar_canvas"] is None and d["avatar_status"] == "UNAVAILABLE"


@pytest.mark.parametrize("spec,role", [("Protection", "TANK"), ("Holy", "HEALING"), ("Frost", "DPS"),
                                       ("Augmentation", "DPS"), ("Preservation", "HEALING"), ("Devourer", "DPS"),
                                       ("Mistweaver", "HEALING"), ("Vengeance", "TANK"), ("Unknown", "")])
def test_role_from_spec(bnet, spec, role):
    s = summary()
    s["active_spec"] = {"name": spec}
    assert run(bnet, FakeBlizzard(**{"": s}))[0].data["role"] == role


def test_role_table_is_complete_and_well_formed():
    from wow.blizzard import SPEC_ROLES
    assert set(SPEC_ROLES.values()) == {"TANK", "HEALING", "DPS"}
    assert len(SPEC_ROLES) >= 35  # 40 specs share some names (Frost, Holy, Restoration, Protection).


# --- Errors, caching, backoff ---------------------------------------------

def test_forbidden_is_not_reported_as_missing_character(bnet):
    result = run(bnet, FakeBlizzard(**{"": 403}))[0]
    assert not result.available
    assert "not found" not in result.error.lower() and "region" in result.error.lower()


def test_character_not_found_mentions_slug(bnet):
    result = run(bnet, FakeBlizzard(**{"": 404}))[0]
    assert not result.available and "slug" in result.error.lower()


def test_rejected_credentials_explain_and_keep_last_good_snapshot(bnet):
    first = run(bnet)[0]
    bnet._blizzard.clear()  # Force a fresh token request.
    with patch("requests.post", return_value=response({"error": "invalid_client"}, 401)), \
         patch("requests.get", side_effect=AssertionError("API call without token")):
        result = bnet.fetch_data()
    assert result.available and result.data["stale"] and result.data["status"] == "STALE"
    assert result.data["mythic_score"] == first.data["mythic_score"]
    assert "client" in result.error.lower()


def test_secrets_never_leak_into_result(bnet):
    results = [run(bnet)[0], run(bnet, FakeBlizzard(**{"": 500}))[0]]
    bnet._blizzard.clear()
    results.append(run(bnet, post=[response({"error": "invalid_client"}, 401)])[0])
    for result in results:
        blob = repr(result.data) + repr(result.error) + repr(result.formatted_lines) + repr(bnet._blizzard)
        assert "secret-456" not in blob and "tok-1" not in blob and "id-123" not in blob


def test_token_is_cached_until_expiry_then_refreshed(bnet):
    with patch("time.monotonic", return_value=1000):
        run(bnet)
        _, _, post = run(bnet, post=AssertionError("token re-requested"))
        assert post.call_count == 0
    with patch("time.monotonic", return_value=1000 + 86399):
        _, _, post = run(bnet)
        assert post.call_count == 1


def test_api_401_invalidates_token_and_retries_once(bnet):
    run(bnet)
    replies = iter([response({}, 401)])
    fake = FakeBlizzard()
    def get(url, **kwargs):
        if url == BASE:
            reply = next(replies, None)
            if reply is not None:
                fake.calls.append((url, kwargs))
                return reply
        return fake(url, **kwargs)
    with patch("requests.post", side_effect=[token()]) as post, patch("requests.get", side_effect=get):
        result = bnet.fetch_data()
    assert result.available and not result.data["stale"]
    assert post.call_count == 1


def test_rate_limit_on_any_call_backs_off_and_keeps_token(bnet):
    run(bnet)
    fake = FakeBlizzard(**{"/encounters/raids": response({}, 429, {"Retry-After": "90"})})
    with patch("requests.post", side_effect=AssertionError("token re-requested")), \
         patch("requests.get", side_effect=fake):
        result = bnet.fetch_data()
    assert result.data["stale"] and "blizzard" in result.error.lower()
    with patch("requests.post", side_effect=AssertionError("network")), \
         patch("requests.get", side_effect=AssertionError("request during backoff")):
        assert bnet.fetch_data().available


def test_credential_change_clears_token_cache(bnet):
    run(bnet)
    bnet.config = {**bnet.config, "client_secret": "rotated"}
    _, _, post = run(bnet)
    assert post.call_count == 1
    assert post.call_args.kwargs["auth"] == ("id-123", "rotated")


def test_source_switch_does_not_reuse_previous_snapshot(bnet):
    run(bnet)
    bnet.config = {**bnet.config, "data_source": "raiderio"}
    with patch("requests.get", side_effect=requests.Timeout):
        assert not bnet.fetch_data().available


# --- Avatar and display ---------------------------------------------------

def test_avatar_uses_character_media_through_trusted_cache(bnet):
    pytest.importorskip("PIL")
    from .test_avatar import image_bytes, image_response
    fake = FakeBlizzard()
    images = []
    def get(url, **kwargs):
        if url == AVATAR:
            images.append(url)
            return image_response(image_bytes("red"))
        return fake(url, **kwargs)
    with patch("requests.post", side_effect=[token()]), patch("requests.get", side_effect=get):
        result = bnet.fetch_data()
    assert images == [AVATAR]
    assert result.data["avatar_status"] == "OK" and result.data["avatar_url"] == AVATAR
    assert {c for row in result.data["avatar_canvas"]["pixels"] for c in row}


def test_inset_is_fallback_when_avatar_missing(bnet):
    pytest.importorskip("PIL")
    m = {"assets": [{"key": "inset", "value": AVATAR}]}
    with patch("wow.download_avatar", side_effect=requests.Timeout) as download:
        run(bnet, FakeBlizzard(**{"/character-media": m}))
    assert download.call_args.args[0] == AVATAR


def test_display_shows_bnet_source_date(bnet):
    with bnet._bound_board(SimpleNamespace(rows=6, cols=22)):
        lines = run(bnet)[0].formatted_lines
    assert lines[-1] == "BNET 2026-10-22"


def test_repeated_api_401_requests_one_new_token_then_fails_stale(bnet):
    run(bnet)
    fake = FakeBlizzard(**{"": 401})
    with patch("requests.post", side_effect=[token(), AssertionError("token loop")]) as post, \
         patch("requests.get", side_effect=fake):
        result = bnet.fetch_data()
    assert post.call_count == 1
    assert sum(1 for u, _ in fake.calls if u == BASE) == 2
    assert result.data["stale"] and "client" in result.error.lower()


@pytest.mark.parametrize("payload", [{}, [], {"name": "Example", "realm": {"name": "R"}}])
def test_bad_summary_does_not_replace_good_snapshot(bnet, payload):
    run(bnet)
    result = run(bnet, FakeBlizzard(**{"": response(payload)}))[0]
    assert result.available and result.data["stale"] and result.data["item_level"] == 281
    assert "invalid" in result.error.lower()


@pytest.mark.parametrize("failure", [requests.Timeout(), response({}, 503)])
def test_token_endpoint_outage_is_unavailable_and_stale(bnet, failure):
    run(bnet)
    bnet._blizzard.clear()
    result = run(bnet, post=[failure])[0]
    assert result.data["stale"] and "unavailable" in result.error.lower()


def test_avatar_cache_keyed_by_url_and_last_login(bnet):
    pytest.importorskip("PIL")
    from .test_avatar import image_bytes, image_response
    downloads = []
    def run_with(summary_payload, color):
        fake = FakeBlizzard(**{"": summary_payload})
        def get(url, **kwargs):
            if url == AVATAR:
                downloads.append(color)
                return image_response(image_bytes(color))
            return fake(url, **kwargs)
        with patch("requests.post", side_effect=[token()]), patch("requests.get", side_effect=get):
            return bnet.fetch_data()
    first = run_with(summary(), "red")
    again = run_with(summary(), "blue")
    assert downloads == ["red"] and again.data["avatar_canvas"] == first.data["avatar_canvas"]
    later = {**summary(), "last_login_timestamp": 1792749600000}
    assert run_with(later, "blue").data["avatar_canvas"] != first.data["avatar_canvas"]
    assert downloads == ["red", "blue"]


@pytest.mark.parametrize("region,locale", [("us", "en-us"), ("kr", "ko-kr"), ("tw", "zh-tw")])
def test_profile_url_locale_per_region(bnet, region, locale):
    bnet.config = {**bnet.config, "region": region}
    fake = FakeBlizzard()
    def get(url, **kwargs):
        return fake(url.replace(f"https://{region}.", "https://eu."), **kwargs)
    with patch("requests.post", side_effect=[token()]), patch("requests.get", side_effect=get):
        d = bnet.fetch_data().data
    assert d["profile_url"] == f"https://worldofwarcraft.blizzard.com/{locale}/character/{region}/example-realm/example"
    assert fake.calls[0][1]["headers"]["Battlenet-Namespace"] == f"profile-{region}"


def test_missing_last_login_is_unknown(bnet):
    s = summary()
    s.pop("last_login_timestamp")
    d = run(bnet, FakeBlizzard(**{"": s}))[0].data
    assert (d["source_updated_at"], d["source_updated_date"], d["source_age_days"]) == ("", "UNKNOWN", None)
    assert d["status"] == "OK"


def test_week_old_login_is_old_data(bnet):
    s = {**summary(), "last_login_timestamp": 1700000000000}
    assert run(bnet, FakeBlizzard(**{"": s}))[0].data["status"] == "OLD DATA"


def test_manifest_declares_source_settings_and_variables():
    import json
    from pathlib import Path
    manifest = json.loads((Path(__file__).parents[1] / "manifest.json").read_text())
    props = manifest["settings_schema"]["properties"]
    assert props["data_source"]["enum"] == ["auto", "raiderio", "blizzard"]
    assert props["data_source"]["default"] == "auto"
    for field in ("client_id", "client_secret"):
        assert props[field]["ui:widget"] == "password"
    assert "source_short" in manifest["variables"]["simple"]
    assert "{{wow.source_short}}" in "".join(manifest["demo"]["template"])


def test_out_of_range_last_login_degrades_to_unknown(bnet):
    s = {**summary(), "last_login_timestamp": 10**20}
    result = run(bnet, FakeBlizzard(**{"": s}))[0]
    assert result.available and result.data["source_updated_date"] == "UNKNOWN"


def test_switching_provider_clears_other_providers_backoff(bnet, profile):
    run(bnet)
    fake = FakeBlizzard(**{"": response({}, 429, {"Retry-After": "600"})})
    with patch("requests.get", side_effect=fake):
        bnet.fetch_data()
    bnet.config = {**bnet.config, "data_source": "raiderio", "realm": "example-realm"}
    with patch("requests.get", return_value=response(profile)) as get:
        result = bnet.fetch_data()
    assert get.called and result.data["source"] == "Raider.IO" and not result.data["stale"]

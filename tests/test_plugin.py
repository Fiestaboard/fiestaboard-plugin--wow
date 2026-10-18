"""Behavior tests with a synthetic public-profile response; no live network."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import pytest
import requests
from wow import WoWPlugin

@pytest.fixture
def plugin():
    p = WoWPlugin({"id":"wow","name":"World of Warcraft","version":"1.0.0"})
    p.config = {"region":"eu","realm":"example-realm","character":"Example","refresh_seconds":900}
    return p

@pytest.fixture
def profile():
    return {
        "name":"Example", "realm":"Example Realm", "region":"eu", "class":"Druid",
        "race":"Night Elf", "active_spec_name":"Restoration", "active_spec_role":"HEALING",
        "faction":"alliance", "achievement_points":12345,
        "profile_url":"https://raider.io/characters/eu/example-realm/Example",
        "last_crawled_at":"2026-10-01T12:00:00.000Z",
        "gear":{"item_level_equipped":250.6}, "guild":{"name":"Example Guild"},
        "mythic_plus_scores_by_season":[{"season":"season-example-2","scores":{"all":2456.7,"healer":2400.1}}],
        "mythic_plus_weekly_highest_level_runs":[
            {"dungeon":"Example Dungeon", "short_name":"ED", "mythic_level":10,"num_keystone_upgrades":0,"score":200},
            {"dungeon":"Another Dungeon", "short_name":"AD", "mythic_level":9,"num_keystone_upgrades":2,"score":190}],
        "raid_progression":{"example-raid":{"summary":"3/8 H","total_bosses":8,"normal_bosses_killed":8,"heroic_bosses_killed":3,"mythic_bosses_killed":0}}
    }

def response(payload=None, status=200, headers=None):
    r = Mock(status_code=status, headers=headers or {})
    r.json.return_value=payload
    if status >= 400:
        r.raise_for_status.side_effect=requests.HTTPError(response=r)
    return r

def fetch(plugin, profile):
    with patch("requests.get", return_value=response(profile)):
        return plugin.fetch_data()

def test_profile_exposes_real_stats_and_separate_source_timestamp(plugin, profile):
    r=fetch(plugin,profile)
    assert r.available
    assert r.data["item_level"] == 250.6
    assert r.data["mythic_score"] == 2456.7
    assert r.data["healer_score"] == 2400.1
    assert r.data["source_updated_at"] == "2026-10-01T12:00:00.000Z"
    assert r.data["fetched_at"] != r.data["source_updated_at"]
    assert r.data["class"] == "Druid"
    assert r.data["guild"] == "Example Guild"
    assert r.data["raid_progress"] == "3/8 H"

def test_highest_completed_key_does_not_claim_it_was_timed(plugin, profile):
    r=fetch(plugin,profile)
    assert r.data["weekly_highest_key"] == 10
    assert r.data["weekly_highest_timed_key"] == 9
    assert r.data["weekly_runs"][0]["timed"] is False

def test_empty_activity_is_not_fabricated_progress(plugin, profile):
    profile["mythic_plus_weekly_highest_level_runs"]=[]
    profile["raid_progression"]={}
    profile["mythic_plus_scores_by_season"]=[{"season":"current","scores":{"all":0,"healer":0}}]
    r=fetch(plugin,profile)
    assert r.data["mythic_score"] == 0
    assert r.data["weekly_highest_key"] is None
    assert r.data["weekly_key_display"] == "--"
    assert r.data["raid_progress"] == "NO DATA"

def test_missing_gear_and_score_remain_unknown(plugin, profile):
    profile.pop("gear")
    profile.pop("mythic_plus_scores_by_season")
    r=fetch(plugin,profile)
    assert r.data["item_level"] is None
    assert r.data["mythic_score"] is None
    assert r.data["item_level_display"] == "--"
    assert r.data["mythic_score_display"] == "--"

def test_timeout_keeps_last_success_and_marks_it_stale(plugin, profile):
    first=fetch(plugin,profile)
    with patch("requests.get",side_effect=requests.Timeout):
        r=plugin.fetch_data()
    assert r.available
    assert r.data["stale"] is True
    assert r.data["status"] == "STALE"
    assert r.data["fetched_at"] == first.data["fetched_at"]
    assert r.data["mythic_score"] == 2456.7
    assert r.error

def test_character_change_does_not_reuse_previous_character(plugin, profile):
    fetch(plugin,profile)
    plugin.config={**plugin.config,"character":"Different"}
    with patch("requests.get",side_effect=requests.Timeout):
        r=plugin.fetch_data()
    assert not r.available
    assert not r.data

def test_rate_limit_obeys_retry_after_without_another_http_call(plugin, profile):
    fetch(plugin,profile)
    with patch("requests.get",return_value=response(status=429,headers={"Retry-After":"120"})):
        r=plugin.fetch_data()
    assert r.data["stale"] is True
    with patch("requests.get",side_effect=AssertionError("request during backoff")):
        assert plugin.fetch_data().available

@pytest.mark.parametrize("payload", [None, [], {}, {"name":"Example","gear":[]}])
def test_bad_payload_does_not_replace_good_snapshot(plugin, profile, payload):
    fetch(plugin,profile)
    r=fetch(plugin,payload)
    assert r.available and r.data["stale"]
    assert r.data["mythic_score"] == 2456.7

def test_not_found_explains_realm_and_region(plugin):
    with patch("requests.get",return_value=response({"message":"Could not find requested character"},400)):
        r=plugin.fetch_data()
    assert not r.available
    assert "realm" in r.error.lower()

@pytest.mark.parametrize("config", [{}, {"region":"xx","realm":"test","character":"Example"}, {"region":"eu","realm":" ","character":"Example"}])
def test_invalid_config_is_rejected_before_network(plugin,config):
    plugin.config=config
    assert plugin.validate_config(config)
    with patch("requests.get",side_effect=AssertionError("invalid configuration reached network")):
        assert not plugin.fetch_data().available

def test_request_uses_current_season_and_encoded_query_parameters(plugin, profile):
    plugin.config={**plugin.config,"realm":"Azjol-Nerub","character":"Éxample"}
    def get(url, **kwargs):
        assert url == "https://raider.io/api/v1/characters/profile"
        assert kwargs["params"]["name"] == "Éxample"
        assert "mythic_plus_scores_by_season:current" in kwargs["params"]["fields"]
        assert "raid_progression:current-tier" in kwargs["params"]["fields"]
        assert kwargs["timeout"] <= 4
        return response(profile)
    with patch("requests.get",side_effect=get):
        assert plugin.fetch_data().available

def test_display_fits_note_and_led_geometry(plugin,profile):
    for rows,cols in [(3,15),(10,16),(6,22)]:
        with plugin._bound_board(SimpleNamespace(rows=rows,cols=cols)):
            r=fetch(plugin,profile)
        assert len(r.formatted_lines) <= rows
        assert all(len(line)<=cols for line in r.formatted_lines)
        assert any("Example" in line for line in r.formatted_lines)


def test_manifest_and_literal_previews_validate_against_core():
    from src.plugins.manifest import validate_manifest, validate_preview_completeness
    manifest=json.loads((Path(__file__).parents[1]/"manifest.json").read_text())
    valid,errors=validate_manifest(manifest)
    assert valid,errors
    assert not validate_preview_completeness(manifest)


def test_config_change_cannot_repopulate_base_cache_with_previous_character(plugin, profile):
    import threading
    started, release, writer_started, changed = (threading.Event() for _ in range(4))
    original_fetch = plugin.fetch_data
    def request(*args, **kwargs):
        started.set()
        assert release.wait(2)
        return response(profile)
    def held_fetch():
        result = original_fetch()
        # Old implementation allows the setter to finish here before base
        # get_data writes its cache. A serialized setter must wait instead.
        changed.wait(.25)
        return result
    def change():
        writer_started.set()
        plugin.config = {**plugin.config, "character":"Different"}
        changed.set()
    with patch.object(plugin, "fetch_data", side_effect=held_fetch), patch("requests.get", side_effect=request):
        reader = threading.Thread(target=plugin.get_data)
        writer = threading.Thread(target=change)
        reader.start()
        assert started.wait(2)
        writer.start()
        assert writer_started.wait(2)
        release.set()
        reader.join(3)
        writer.join(3)
        assert not reader.is_alive() and not writer.is_alive()
    updated={**profile,"name":"Different"}
    with patch("requests.get",return_value=response(updated)):
        assert plugin.get_data().data["name"] == "Different"

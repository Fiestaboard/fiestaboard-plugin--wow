"""Shared fixtures: a configured plugin and a synthetic Raider.IO profile."""
from unittest.mock import Mock

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

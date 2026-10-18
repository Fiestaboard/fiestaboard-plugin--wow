# World of Warcraft Setup Guide

Show a Retail character's stats using Raider.IO.

## Overview

Requires FiestaBoard 9.0.0 or newer, internet access, and a character indexed on [Raider.IO](https://raider.io). No credentials are needed. Classic is not supported by this plugin.

## Quick Setup

1. Install **World of Warcraft** from Integrations, or install `https://github.com/Fiestaboard/fiestaboard-plugin--world-of-warcraft` with plugin ID `wow`.
2. Open the character's Raider.IO profile. A URL like `/characters/eu/realm-name/Character` gives the region, realm and exact name. Configure those fields, then enable the plugin.
3. Create the plugin's demo page or insert `{{wow.name}}`, `{{wow.item_level_display}}` and `{{wow.mythic_score_display}}` in your own page.
4. Preview and assign the page to a board. Include `{{wow.source_updated_date}}` so viewers can judge freshness.

For the Divoom/AI-art layout, see the [example page](../examples/pixoo-character-and-art.json) and [README](../README.md#example-templates). The art source requires Generative AI Art to be installed, enabled and configured. Missing art does not prevent stats from loading. The JSON is page content for the page API/editor, not a separate plugin configuration or a guaranteed share-import file.

## Template Variables

| Variable | Meaning |
|---|---|
| `name` | Character name |
| `realm` | Realm |
| `region` | Region |
| `class` | Class |
| `spec` | Active specialization |
| `role` | Active role |
| `race` | Race |
| `faction` | Faction |
| `guild` | Guild |
| `achievement_points` | Achievement points |
| `item_level` | Equipped item level; null when unavailable |
| `item_level_display` | Rounded item level or -- |
| `season` | Season returned by Raider.IO |
| `mythic_score` | Overall current-season Mythic+ score; null when unavailable |
| `mythic_score_display` | Rounded score or -- |
| `healer_score` | Current-season healer score; null when unavailable |
| `weekly_highest_key` | Highest completed key this week, including untimed runs |
| `weekly_highest_timed_key` | Highest timed key this week |
| `weekly_key_display` | Highest completed key formatted as +N, or -- |
| `raid_progress` | Current-tier raid summaries, separated by | |
| `source` | Data provider name |
| `profile_url` | Raider.IO character profile and attribution link |
| `source_updated_at` | Timestamp when Raider.IO last crawled the character |
| `source_updated_date` | Source date, YYYY-MM-DD, or UNKNOWN |
| `source_age_days` | Age of the source snapshot in days; null if unknown |
| `fetched_at` | Timestamp of our last successful fetch, not the source update time |
| `stale` | True when showing a saved snapshot after a failed refresh |
| `status` | OK, OLD DATA (source older than seven days), or STALE (refresh failed) |

`weekly_runs` and `raids` expose the run and raid arrays; see the README for fields.

## Configuration Reference

| Setting | Default | Description |
|---|---|---|
| `region` | `eu` | Retail region: eu, us, kr, tw |
| `realm` | Required | Realm name or slug from the profile URL |
| `character` | Required | Exact character name, including accents |
| `refresh_seconds` | `900` | Poll interval, 300–86400 seconds |

No environment variables, API keys, or account permissions are used.

## Troubleshooting

- **Character not found:** Check region, realm, accents and spelling on Raider.IO. Names are not unique across realms. The profile must be Retail and indexed by Raider.IO.
- **OLD DATA:** The source snapshot is older than seven days. A successful FiestaBoard poll does not make upstream data fresh. Visit the linked Raider.IO profile to inspect its update status.
- **STALE:** A refresh failed; the last successful snapshot remains visible. It is held in memory and is cleared when configuration changes or the process restarts.
- **-- / NO DATA:** A requested field or activity record was not supplied. This is distinct from a real zero score.
- **Rate limit:** The plugin waits for Retry-After and tries again on a subsequent refresh. Leave the default 15-minute poll interval unless you have a reason to change it.
- **Art is blank:** Check Generative AI Art separately and save a known-good canvas fallback. Text and art refresh independently.
- **Healing stats:** `healer_score` is a Mythic+ role score, not healing-per-second. This plugin does not fetch Warcraft Logs or invent combat performance.

Data supplied by [Raider.IO](https://raider.io). Include that attribution link in public dashboard documentation.

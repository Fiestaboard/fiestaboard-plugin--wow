# World of Warcraft Setup Guide

Show a Retail character's stats using Raider.IO.

## Overview

Text stats require FiestaBoard 9.0.0 or newer, internet access, and a character indexed on [Raider.IO](https://raider.io). No credentials are needed. Classic is not supported by this plugin.

## Quick Setup

1. Install **World of Warcraft** from Integrations, or install `https://github.com/Fiestaboard/fiestaboard-plugin--wow` with plugin ID `wow`.
2. Open the character's Raider.IO profile. A URL like `/characters/eu/realm-name/Character` gives the region, realm and exact name. Configure those fields, then enable the plugin.
3. Create the plugin's demo page or insert `{{wow.name}}`, `{{wow.item_level_display}}` and `{{wow.mythic_score_display}}` in your own page.
4. Preview and assign the page to a board. Include `{{wow.source_updated_date}}` so viewers can judge freshness.

For the Divoom/AI-art layout, see the [example page](../examples/pixoo-character-and-art.json) and [README](../README.md#example-templates). The art source requires Generative AI Art to be installed, enabled and configured. Missing art does not prevent stats from loading. The JSON is page content for the page API/editor, not a separate plugin configuration or a guaranteed share-import file.

## Character portrait canvas

Set a page canvas’s Source to `{{wow.avatar_canvas}}`. Adjust its area in the canvas editor; use **Avatar pixel width/height** in the WoW integration settings for source resolution (default 64×64, maximum 128×128). A rectangular source crops the image without stretching. For a whole 64×64 Pixoo, cover all 10×16 text cells with bleed on all sides and scale 1.

See the [small portrait example](../examples/pixoo-character-and-avatar.json), [full-display example](../examples/pixoo-avatar-full-display.json), and [sizing/caching details](../README.md#real-character-avatar). No Generative AI Art instance is needed for the real portrait. Avatar decoding requires FiestaBoard 10.0.0-beta.59 or newer on `next`, which ships Pillow. Older runtimes keep stats working with `avatar_status=UNAVAILABLE`.

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
| `avatar_canvas` | Actual Blizzard portrait as pixel canvas content; null when unavailable |
| `avatar_status` | OK, STALE (cached portrait), or UNAVAILABLE |
| `avatar_url` | Source Blizzard image URL for the displayed portrait |

`weekly_runs` and `raids` expose the run and raid arrays; see the README for fields.

## Configuration Reference

| Setting | Default | Description |
|---|---|---|
| `region` | `eu` | Retail region: eu, us, kr, tw |
| `realm` | Required | Realm name or slug from the profile URL |
| `character` | Required | Exact character name, including accents |
| `refresh_seconds` | `900` | Poll interval, 300–86400 seconds |
| `avatar_width` | `64` | Source pixel width, 1–128 |
| `avatar_height` | `64` | Source pixel height, 1–128 |

No environment variables, API keys, or account permissions are used.

## Troubleshooting

- **Character not found:** Check region, realm, accents and spelling on Raider.IO. Names are not unique across realms. The profile must be Retail and indexed by Raider.IO.
- **OLD DATA:** The source snapshot is older than seven days. A successful FiestaBoard poll does not make upstream data fresh. Visit the linked Raider.IO profile to inspect its update status.
- **STALE:** A refresh failed; the last successful snapshot remains visible. It is held in memory and is cleared when configuration changes or the process restarts.
- **-- / NO DATA:** A requested field or activity record was not supplied. This is distinct from a real zero score.
- **Rate limit:** The plugin waits for Retry-After and tries again on a subsequent refresh. Leave the default 15-minute poll interval unless you have a reason to change it.
- **Avatar is blank:** Check `avatar_status` and the character’s Raider.IO portrait. The avatar requires a pixel canvas on a compatible build, not a text template cell. Save known-good canvas content as fallback. A missing portrait never blocks stats.
- **AI art is blank:** Check Generative AI Art separately and save a known-good canvas fallback. Text and art refresh independently.
- **Healing stats:** `healer_score` is a Mythic+ role score, not healing-per-second. This plugin does not fetch Warcraft Logs or invent combat performance.

Data supplied by [Raider.IO](https://raider.io). Include that attribution link in public dashboard documentation.

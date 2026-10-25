# World of Warcraft Setup Guide

Show a Retail character's stats using Raider.IO, or Blizzard’s official API for fresher data.

## Overview

Text stats require FiestaBoard 9.0.0 or newer, internet access, and a character indexed on [Raider.IO](https://raider.io), or Battle.net API credentials for Blizzard’s Profile API. No credentials are needed for Raider.IO; Blizzard’s API needs a free Battle.net API client. Classic is not supported by this plugin.

## Quick Setup

1. Install **World of Warcraft** from Integrations, or install `https://github.com/Fiestaboard/fiestaboard-plugin--wow` with plugin ID `wow`.
2. Open the character's Raider.IO profile. A URL like `/characters/eu/realm-name/Character` gives the region, realm and exact name. Configure those fields, then enable the plugin.
3. Create the plugin's demo page or insert `{{wow.name}}`, `{{wow.item_level_display}}` and `{{wow.mythic_score_display}}` in your own page.
4. Preview and assign the page to a board. Include `{{wow.source_updated_date}}` so viewers can judge freshness.

For the Divoom/AI-art layout, see the [example page](../examples/pixoo-character-and-art.json) and [README](../README.md#example-templates). The art source requires Generative AI Art to be installed, enabled and configured. Missing art does not prevent stats from loading. The JSON is page content for the page API/editor, not a separate plugin configuration or a guaranteed share-import file.

## Optional: fresher data from Blizzard

Raider.IO updates when it re-crawls a character, which can take hours or days. Blizzard’s official Profile API updates when the character logs out. Using Blizzard is optional: without it, the plugin works as above with Raider.IO and needs no account.

### Who needs to do this

Only people who want the fresher data. **Each FiestaBoard owner creates their own free Battle.net API client.** FiestaBoard does not ship a shared client, because the plugin is open source and any secret bundled with it would be public. Your credentials stay in your own board’s settings.

### 1. Create a Battle.net API client

Sign in at [develop.battle.net](https://develop.battle.net/access/clients), open **API Access**, and choose **Create Client**. It is free and available immediately; there is nothing to apply for. Blizzard may ask you to add an authenticator to your account first.

| Field | What to enter |
|---|---|
| **Client Name** | Anything unique to you, such as `FiestaBoard WoW - YourName`. Names are unique across all Battle.net developer accounts, so a plain “FiestaBoard” is likely taken. |
| **Redirect URLs** | Required by the form but unused by this plugin. Enter `https://fiestaboard.app/auth/oauth/redirect`. |
| **Service URL** | Tick **I do not have a service URL**. Your board calls the API from your home network, not from a hosted service. |
| **Intended Use** | For example: “Personal FiestaBoard display. A self-hosted board on my home network uses the client-credentials grant to read public WoW Profile API data for my character every 5–15 minutes. No end-user login; nothing stored beyond an in-memory cache.” |

Save, then copy the **Client ID** and **Client Secret** from the Credentials section.

### 2. Add the credentials to your board

1. In FiestaBoard, open the World of Warcraft integration settings.
2. Paste the **Battle.net client ID** and **Battle.net client secret**. Leave **Data source** on `auto`.
3. Set **Realm** to the slug from your Armory URL, for example `argent-dawn` in `worldofwarcraft.blizzard.com/en-gb/character/eu/argent-dawn/name`. Accented Latin names are converted automatically, but Russian, Korean and Taiwanese realms must be entered as the slug.
4. Save. The bottom line of the demo page changes from `RIO <date>` to `BNET <date>`, where the date is the character’s last logout.

After saving, both credential fields show `***`, including the client ID. Leaving a field as `***` keeps the stored value; type over it to replace it. See the [README](../README.md#fresher-data-with-blizzards-api-optional) for exactly which variables differ between sources.

### Keep the secret private

- Paste the secret only into your board’s settings. Do not put it in a page template, a shared page export, an issue, a chat, or a Git repository.
- The board stores it in its own configuration and masks it in the settings UI and API responses. The plugin never puts it in template variables, error messages or logs, and only sends it to Blizzard’s token endpoint (`oauth.battle.net`).
- If the secret is ever exposed, open the client at develop.battle.net, reset the secret, and paste the new one into your board.
- To stop using Blizzard, clear both fields or set **Data source** to `raiderio`.

### How the credentials are used

The plugin uses OAuth’s **client-credentials** grant: it exchanges the client ID and secret for an app token (valid about 24 hours, cached in memory) and reads public character data with it. Nobody signs in to Battle.net, no browser redirect happens, and the FiestaBoard OAuth relay is not involved. Each refresh makes up to four API calls, far below Blizzard’s per-client limit of 36,000 per hour.

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
| `role` | Active role (TANK, HEALING or DPS) |
| `race` | Race |
| `faction` | Faction |
| `guild` | Guild |
| `achievement_points` | Achievement points |
| `item_level` | Equipped item level; null when unavailable |
| `item_level_display` | Rounded item level or -- |
| `season` | Current Mythic+ season (Raider.IO slug or Blizzard season ID) |
| `mythic_score` | Overall current-season Mythic+ score (Raider.IO score or Blizzard rating); null when unavailable |
| `mythic_score_display` | Rounded score or -- |
| `healer_score` | Current-season healer score (Raider.IO only); null when unavailable |
| `weekly_highest_key` | Highest completed key this week, including untimed runs |
| `weekly_highest_timed_key` | Highest timed key this week |
| `weekly_key_display` | Highest completed key formatted as +N, or -- |
| `raid_progress` | Current-tier raid summaries, separated by | |
| `source` | Data provider name: Raider.IO or Blizzard |
| `source_short` | Short provider label: RIO or BNET |
| `profile_url` | Raider.IO or Blizzard Armory character profile link |
| `source_updated_at` | Raider.IO crawl time, or the character’s last logout for Blizzard |
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
| `data_source` | `auto` | `auto`, `raiderio`, or `blizzard` |
| `client_id` | Empty | Optional Battle.net API client ID |
| `client_secret` | Empty | Optional Battle.net API client secret |
| `character` | Required | Exact character name, including accents |
| `refresh_seconds` | `900` | Poll interval, 300–86400 seconds |
| `avatar_width` | `64` | Source pixel width, 1–128 |
| `avatar_height` | `64` | Source pixel height, 1–128 |

No environment variables are used. Raider.IO needs no key; the optional Blizzard source uses a Battle.net API client ID and secret stored as masked plugin settings.

## Troubleshooting

- **Character not found:** Check region, realm, accents and spelling on Raider.IO. Names are not unique across realms. The profile must be Retail and indexed by Raider.IO.
- **OLD DATA:** The source snapshot is older than seven days. With Blizzard, this means the character has not logged out in seven days. A successful FiestaBoard poll does not make upstream data fresh. Visit the linked Raider.IO profile to inspect its update status.
- **Blizzard rejected the client ID or secret:** Recreate or re-copy both values from develop.battle.net. Entering only one is rejected.
- **Blizzard: character not found:** Use the realm slug from the Armory URL and check the region. Blizzard also returns not-found for characters inactive for a very long time, even if Raider.IO still lists them.
- **Blizzard refused access:** The region probably does not match the realm.
- **STALE:** A refresh failed; the last successful snapshot remains visible. It is held in memory and is cleared when configuration changes or the process restarts.
- **-- / NO DATA:** A requested field or activity record was not supplied. This is distinct from a real zero score.
- **Rate limit:** The plugin waits for Retry-After and tries again on a subsequent refresh. Leave the default 15-minute poll interval unless you have a reason to change it.
- **Avatar is blank:** Check `avatar_status` and the character’s Raider.IO portrait. The avatar requires a pixel canvas on a compatible build, not a text template cell. Save known-good canvas content as fallback. A missing portrait never blocks stats.
- **AI art is blank:** Check Generative AI Art separately and save a known-good canvas fallback. Text and art refresh independently.
- **Healing stats:** `healer_score` is a Mythic+ role score, not healing-per-second. This plugin does not fetch Warcraft Logs or invent combat performance.

Data supplied by [Raider.IO](https://raider.io) or Blizzard Entertainment’s Battle.net API, depending on the source. Include the matching attribution in public dashboard documentation.

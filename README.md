# World of Warcraft Plugin

Display Retail character stats from Raider.IO alongside your FiestaBoard content.

![World of Warcraft Display](./docs/board-display.png)

Captured from FiestaBoard’s rendered 64×64 output: a generated Druid portrait beside real Raider.IO stats for the Anorak–Bronzebeard demo. This is a rendering of the sent frame, not a photograph of the device.

**→ [Setup Guide](./docs/SETUP.md)**

## Overview

Track one configurable Retail character with the public [Raider.IO API](https://raider.io/api). No API key or Battle.net login is required. Character data updates periodically; this plugin exposes both the source update time and the time FiestaBoard fetched it.

## Template Variables

Prefix all variables with `wow.`. Numeric values are null when unknown; the corresponding display variables show `--`. A reported score of zero remains zero.

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

`weekly_runs` contains dungeon, short_name, level, timed, and score. `raids` contains slug, name, summary, total_bosses, normal_bosses_killed, heroic_bosses_killed, and mythic_bosses_killed. Index arrays as `{{wow.raids.0.summary}}`.

## Example Templates

```text
{{wow.name}}
{{wow.spec}} {{wow.class}}
ILVL {{wow.item_level_display}}  M+ {{wow.mythic_score_display}}
WEEK {{wow.weekly_key_display}}
{{wow.raid_progress}}
RIO {{wow.source_updated_date}}
```

[Pixoo character and AI art example](./examples/pixoo-character-and-art.json) reserves a smaller canvas beside the stats. It requires the separate Generative AI Art plugin and a pixel-capable FiestaBoard build with page canvases. Create a named `wow` instance of Generative AI Art, configure and enable it independently, then set its custom theme to your character's class, race and specialization, such as “World of Warcraft Restoration Druid, emerald healing magic, moonlit forest, bold silhouette, no lettering.” The example uses `{{generative_ai_art:wow.canvas}}`, keeping its theme separate from the base art instance. Canvases sharing the same instance share its artwork; create different instances for different themes. The image is scaled into the region; native generation at that region's dimensions is not provided by this stats plugin. Save a generated image as the canvas's content fallback to keep it visible while the art source refreshes.

Numbers in the registry previews are illustrative. The running plugin always reads API data; it does not generate stats with AI. A character's active spec can differ from the role used for previous runs.

## Configuration

| Setting | Default | Description |
|---|---|---|
| `region` | `eu` | Retail region: eu, us, kr, tw |
| `realm` | Required | Realm name or slug from the profile URL |
| `character` | Required | Exact character name, including accents |
| `refresh_seconds` | `900` | Poll interval, 300–86400 seconds |

## Features

- Retail character identity, equipped item level, achievements and guild.
- Current-season overall and healer Mythic+ scores.
- Highest completed and highest timed weekly keys, kept separate.
- Progress for all raids returned for the current tier.
- Last successful snapshot retained after failed refreshes, explicitly marked STALE.
- Server Retry-After respected on HTTP 429; short request timeout.
- Text output adapts to the board's rows and columns.
- Composes with a separate AI-art canvas on pixel displays.

This is not live combat telemetry, a complete weekly run history, or a Great Vault tracker. Raider.IO returns up to ten highest weekly runs, not every run. Empty arrays mean no records returned, not proof that the character has done no content. Old source snapshots show OLD DATA. Public-facing uses must retain a [Raider.IO](https://raider.io) attribution link; `profile_url` provides a character-specific link.

## Author

FiestaBoard Team. World of Warcraft is a trademark of Blizzard Entertainment. This community integration is not affiliated with Blizzard or Raider.IO.

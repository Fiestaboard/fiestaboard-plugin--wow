# WoW avatar canvas implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose the real character portrait as an adjustable `wow.avatar_canvas`, usable beside stats or across a whole display.

**Architecture:** Download the Blizzard thumbnail supplied by Raider.IO. Convert it with Pillow into bounded palette pixels, preserving proportions with a centered crop. Cache the last good source separately from stats; existing page canvas placement controls its on-screen area.

**Tech Stack:** Python, requests, Pillow, FiestaBoard canvas content, pytest, GitHub Actions.

**Spec:** User-approved in-chat design: actual avatar, adjustable small/full-display resolution, last-good caching, live Anorak–Bronzebeard example.

## Global constraints

- Keep existing stats and AI-art examples compatible; no core or FiestaUI change required.
- Width and height each 1–128 pixels, default 64; at most 62 palette colors.
- Only HTTPS Blizzard render hosts; no redirects, bounded image download and decoding.
- Do not alter local Docker; test in CI while it is unavailable.

## Review focus

- Missing/corrupt avatar must not suppress valid stats (plugin tests).
- Character changes must discard previous avatar (cache isolation test).
- A stable URL can serve new gear: invalidate on source timestamp or six-hour TTL (cache tests).
- Non-square dimensions must crop without stretching (converter tests).
- Nested and full-display examples must render via real core canvas models (integration tests on next).

### Task 1: Avatar pipeline and plugin integration

Files: create `avatar.py`, `tests/test_avatar.py`; modify `__init__.py`, `manifest.json`, `requirements.txt`, docs and examples.

Interfaces: `avatar_canvas(image_bytes, width, height) -> dict`; `download_avatar(url) -> bytes`; plugin adds `avatar_canvas`, `avatar_status`, `avatar_url`.

- [ ] Write behavior tests for conversion, fetch boundaries, caching, failure isolation, sizing and real rendering.
- [ ] Run test-only branch in existing CI and observe missing feature failure.
- [ ] Implement conversion, validated download, cache integration, settings and documentation.
- [ ] Run full suite against core main and next with existing 80% coverage gate.
- [ ] Review, merge and release plugin 1.1.0.
- [ ] Back up Pi, update only WoW plugin, switch demo portrait source, verify live output and a full-display example.

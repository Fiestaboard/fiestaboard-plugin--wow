"""Portrait fidelity, bounded fetching, and cache isolation at public boundaries."""
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

from .test_plugin import plugin, profile, response

URL = "https://render.worldofwarcraft.com/eu/character/example/1/2-avatar.jpg"


def image_bytes(color="red", size=(84, 84)):
    image = Image.new("RGB", size, color)
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def image_response(data):
    result = response()
    result.iter_content.return_value = [data]
    result.close = Mock()
    return result


def fetch_avatar(plugin, profile, image=None):
    profile = {**profile, "thumbnail_url": URL}
    replies = [response(profile)]
    if image is not None:
        replies.append(image_response(image))
    with patch("requests.get", side_effect=replies) as get:
        result = plugin.fetch_data()
    return result, get


@pytest.mark.parametrize("width,height", [(1, 1), (31, 29), (64, 64), (128, 128)])
def test_avatar_canvas_has_requested_dimensions_and_true_source_color(plugin, profile, width, height):
    plugin.config = {**plugin.config, "avatar_width": width, "avatar_height": height}
    result, _ = fetch_avatar(plugin, profile, image_bytes())
    canvas = result.data["avatar_canvas"]
    assert result.available and result.data["avatar_status"] == "OK"
    assert canvas["size"] == [width, height]
    assert len(canvas["pixels"]) == height
    assert all(len(row) == width for row in canvas["pixels"])
    assert {canvas["palette"][char] for row in canvas["pixels"] for char in row} == {"#ff0000"}


def test_rectangular_crop_keeps_center_without_squashing():
    from wow.avatar import avatar_canvas
    im = Image.new("RGB", (12, 4), "red")
    im.paste("blue", (4, 0, 8, 4))
    out = BytesIO()
    im.save(out, format="PNG")
    canvas = avatar_canvas(out.getvalue(), 4, 4)
    assert {canvas["palette"][c] for row in canvas["pixels"] for c in row} == {"#0000ff"}


def test_unavailable_avatar_does_not_hide_stats(plugin, profile):
    with patch("requests.get", return_value=response(profile)):
        result = plugin.fetch_data()
    assert result.available and result.data["item_level"] == 250.6
    assert result.data["avatar_canvas"] is None
    assert result.data["avatar_status"] == "UNAVAILABLE"


@pytest.mark.parametrize("failure", [requests.Timeout(), b"not an image"])
def test_avatar_failure_preserves_portrait_and_refreshes_stats(plugin, profile, failure):
    first, _ = fetch_avatar(plugin, profile, image_bytes())
    profile = {**profile, "thumbnail_url": URL, "last_crawled_at": "2026-10-18T12:00:00Z", "gear": {"item_level_equipped": 300}}
    reply = failure if isinstance(failure, Exception) else image_response(failure)
    with patch("requests.get", side_effect=[response(profile), reply]):
        result = plugin.fetch_data()
    assert result.available and result.data["item_level"] == 300
    assert result.data["avatar_canvas"] == first.data["avatar_canvas"]
    assert result.data["avatar_status"] == "STALE"


def test_cache_reuses_original_when_resizing_but_not_for_other_character(plugin, profile):
    fetch_avatar(plugin, profile, image_bytes())
    plugin.config = {**plugin.config, "avatar_width": 24, "avatar_height": 32}
    result, get = fetch_avatar(plugin, profile)
    assert result.data["avatar_canvas"]["size"] == [24, 32]
    assert get.call_count == 1  # Profile only; image is already cached.
    plugin.config = {**plugin.config, "character": "Different"}
    with patch("requests.get", side_effect=[response({**profile, "name": "Different", "thumbnail_url": URL}), requests.Timeout()]):
        result = plugin.fetch_data()
    assert result.data["name"] == "Different"
    assert result.data["avatar_canvas"] is None


def test_same_url_refreshes_on_source_timestamp_and_after_six_hours(plugin, profile):
    with patch("time.monotonic", return_value=100):
        first, _ = fetch_avatar(plugin, profile, image_bytes("red"))
        cached, get = fetch_avatar(plugin, profile)
        assert get.call_count == 1 and cached.data["avatar_canvas"] == first.data["avatar_canvas"]
        profile = {**profile, "last_crawled_at": "2026-10-18T12:00:00Z"}
        updated, get = fetch_avatar(plugin, profile, image_bytes("blue"))
        assert get.call_count == 2 and updated.data["avatar_canvas"] != first.data["avatar_canvas"]
    with patch("time.monotonic", return_value=21701):
        refreshed, get = fetch_avatar(plugin, profile, image_bytes("green"))
        assert get.call_count == 2 and refreshed.data["avatar_canvas"] != updated.data["avatar_canvas"]


@pytest.mark.parametrize("field,value", [("avatar_width", 0), ("avatar_height", 129), ("avatar_width", True), ("avatar_width", 2.5), ("avatar_height", "64")])
def test_invalid_sizes_rejected_before_network(plugin, field, value):
    plugin.config = {**plugin.config, field: value}
    with patch("requests.get", side_effect=AssertionError("invalid settings reached network")):
        assert not plugin.fetch_data().available


@pytest.mark.parametrize("url", ["http://render.worldofwarcraft.com/a", "https://example.com/a", "https://render.worldofwarcraft.com.evil.test/a", "https://user@render.worldofwarcraft.com/a", "https://render.worldofwarcraft.com:444/a", None])
def test_untrusted_avatar_url_never_downloaded(plugin, profile, url):
    with patch("requests.get", side_effect=[response({**profile, "thumbnail_url": url})]) as get:
        result = plugin.fetch_data()
    assert result.available and result.data["avatar_canvas"] is None
    assert get.call_count == 1


def test_redirect_is_not_followed_and_response_is_closed():
    from wow.avatar import download_avatar
    redirect = response(status=302, headers={"Location": "http://127.0.0.1/"})
    with patch("requests.get", return_value=redirect) as get, pytest.raises(ValueError):
        download_avatar(URL)
    assert get.call_args.kwargs["allow_redirects"] is False
    redirect.close.assert_called_once()


def test_download_limit_applies_even_without_content_length():
    from wow.avatar import download_avatar
    oversized = image_response(b"x" * (2 * 1024 * 1024 + 1))
    with patch("requests.get", return_value=oversized), pytest.raises(ValueError):
        download_avatar(URL)
    oversized.close.assert_called_once()


def test_decode_rejects_oversized_image_before_loading_pixels():
    from wow.avatar import avatar_canvas
    with pytest.raises(ValueError):
        avatar_canvas(image_bytes(size=(2049, 1)), 64, 64)


def test_palette_and_examples_render_on_real_pixel_canvas():
    import json
    from pathlib import Path
    from wow.avatar import avatar_canvas
    models = pytest.importorskip("src.canvas.models")  # Canvas is introduced in core next.
    from src.canvas.geometry import canvas_placement
    from src.canvas.raster import render_content
    from src.led.matrix import grid_layout
    im = Image.new("RGB", (84, 84))
    im.putdata([(x * 3, y * 3, (x + y) % 256) for y in range(84) for x in range(84)])
    out = BytesIO()
    im.save(out, format="PNG")
    content = models.CanvasContent.model_validate(avatar_canvas(out.getvalue(), 64, 64))
    assert 1 < len(content.palette) <= 62
    for filename, size in [("pixoo-character-and-avatar.json", (31, 29)), ("pixoo-avatar-full-display.json", (64, 64))]:
        example = json.loads((Path(__file__).parents[1] / "examples" / filename).read_text())
        canvas = models.Canvas.model_validate(example["canvases"][0])
        place = canvas_placement(canvas, grid_layout(64, 64, "3x5"))
        assert (place.width, place.height) == size
        rgba = render_content(content, place.width, place.height)
        assert len(rgba) == size[0] * size[1] * 4
        assert any(rgba[3::4])

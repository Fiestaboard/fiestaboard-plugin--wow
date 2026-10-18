"""Bounded Blizzard portrait downloads and deterministic palette pixel conversion."""
from io import BytesIO
from urllib.parse import urlsplit

import requests
try:
    from PIL import Image, ImageOps
except ImportError:  # Older cores still support the character's text stats.
    Image = ImageOps = None

DECODE_ERRORS = (OSError, ValueError) + ((Image.DecompressionBombError,) if Image else ())

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_EDGE = 2048
PALETTE_KEYS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
RENDER_HOSTS = {"render.worldofwarcraft.com", *(f"render-{region}.worldofwarcraft.com" for region in ("eu", "us", "kr", "tw"))}


def image_decoder_available() -> bool:
    return Image is not None


def trusted_avatar_url(value) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.hostname in RENDER_HOSTS
                and url.port in (None, 443) and not url.username and not url.password
                and not any(ord(c) <= 32 for c in value))
    except ValueError:
        return False


def download_avatar(url: str) -> bytes:
    if not trusted_avatar_url(url):
        raise ValueError("Untrusted avatar URL")
    response = requests.get(url, timeout=3, stream=True, allow_redirects=False)
    try:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Avatar response must be a direct image")
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Avatar download is too large")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            data.extend(chunk)
            if len(data) > MAX_DOWNLOAD_BYTES:
                raise ValueError("Avatar download is too large")
        return bytes(data)
    finally:
        response.close()


def avatar_canvas(image_bytes: bytes, width: int = 64, height: int = 64) -> dict:
    """Fill the requested pixel rectangle with a centered crop, never stretch."""
    if not image_decoder_available():
        raise ValueError("This FiestaBoard runtime does not include image decoding")
    if any(isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 128 for v in (width, height)):
        raise ValueError("Avatar dimensions must be integers from 1 to 128")
    if len(image_bytes) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Avatar download is too large")
    with Image.open(BytesIO(image_bytes)) as original:
        if max(original.size) > MAX_IMAGE_EDGE:
            raise ValueError("Avatar image dimensions are too large")
        # Decode only the first frame. The character portrait is already a
        # head-and-shoulders crop; further cropping only matches aspect ratio.
        image = ImageOps.exif_transpose(original).convert("RGB")
        image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        quantized = image.quantize(colors=len(PALETTE_KEYS), dither=Image.Dither.NONE)
    palette = quantized.getpalette()
    indices = quantized.tobytes()
    colors = {PALETTE_KEYS[i]: "#%02x%02x%02x" % tuple(palette[3*i:3*i+3]) for i in sorted(set(indices))}
    pixels = ["".join(PALETTE_KEYS[i] for i in indices[y*width:(y+1)*width]) for y in range(height)]
    return {"size": [width, height], "palette": colors, "pixels": pixels}

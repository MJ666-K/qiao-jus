import base64
import random
import time
import uuid

_EXPIRE_SECONDS = 300
_CODE_LENGTH = 4
_WIDTH = 120
_HEIGHT = 44
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_PURGE_INTERVAL = 10

_store: dict[str, tuple[str, float]] = {}
_last_purge: float = 0.0


def _purge() -> None:
    global _last_purge
    now = time.time()
    if now - _last_purge < _PURGE_INTERVAL:
        return
    _last_purge = now
    for k in [k for k, (_, exp) in _store.items() if exp < now]:
        _store.pop(k, None)


def _color() -> str:
    return "#%02x%02x%02x" % (
        random.randint(30, 120),
        random.randint(30, 120),
        random.randint(90, 170),
    )


def _render_svg(code: str) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{_HEIGHT}" viewBox="0 0 {_WIDTH} {_HEIGHT}">',
        f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="#f8fafc"/>',
    ]
    for _ in range(28):
        parts.append(
            f'<circle cx="{random.randint(0, _WIDTH)}" cy="{random.randint(0, _HEIGHT)}" '
            f'r="1" fill="{_color()}" opacity="0.5"/>'
        )
    for _ in range(4):
        parts.append(
            f'<line x1="{random.randint(0, _WIDTH)}" y1="{random.randint(0, _HEIGHT)}" '
            f'x2="{random.randint(0, _WIDTH)}" y2="{random.randint(0, _HEIGHT)}" '
            f'stroke="{_color()}" stroke-width="1" opacity="0.5"/>'
        )
    char_width = _WIDTH / (_CODE_LENGTH + 1)
    for i, ch in enumerate(code):
        x = char_width * (i + 1)
        y = _HEIGHT / 2 + random.randint(-4, 4)
        rot = random.randint(-18, 18)
        size = random.randint(22, 28)
        parts.append(
            f'<text x="{x}" y="{y}" font-family="Verdana, Geneva, sans-serif" font-size="{size}" '
            f'font-weight="bold" text-anchor="middle" dominant-baseline="middle" '
            f'fill="{_color()}" transform="rotate({rot} {x} {y})">{ch}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def create_captcha() -> tuple[str, str]:
    _purge()
    code = "".join(random.choices(_ALPHABET, k=_CODE_LENGTH))
    key = uuid.uuid4().hex
    _store[key] = (code.lower(), time.time() + _EXPIRE_SECONDS)
    svg = _render_svg(code)
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return key, f"data:image/svg+xml;base64,{b64}"


def verify_captcha(key: str, code: str) -> bool:
    _purge()
    entry = _store.pop(key, None)
    if entry is None:
        return False
    expected, _ = entry
    return expected == code.strip().lower()

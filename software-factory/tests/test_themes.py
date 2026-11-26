import re
from conftest import SF

WEB = SF / "lib" / "factory" / "web"
CSS = (WEB / "themes.css").read_text() if (WEB / "themes.css").exists() else ""
NEXTORIAN_DARK = ':root, [data-palette="nextorian"]'
NEXTORIAN_LIGHT = ':root[data-theme="light"], [data-palette="nextorian"][data-theme="light"]'
TOKENS = """bg top fg muted muted-strong soft column panel panel-line line raised done accent accent-hover link link-hover
brand-pink yellow err err-line err-bg ok active-bg active-fg active-dot approval-bg approval-fg approval-dot attn-bg attn-fg
attn-dot attn-line wait-bg wait-fg wait-dot neutral-fg paused-dot tab-on shadow bot-band bot-eye accent-fg check-fg banner-fg
pill-active-bg pill-active-fg pill-approval-bg pill-approval-fg pill-attn-bg pill-attn-fg pill-wait-bg pill-wait-fg
switch-track-off switch-knob-off switch-knob-on term-bg term-line term-cursor term-selection""".split()


def blocks():
    out = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)):
        decls = dict((k.strip(), v.strip()) for k, v in (d.split(":", 1) for d in body.split(";") if ":" in d))
        out[" ".join(sel.split())] = {k[2:] if k.startswith("--") else k: v for k, v in decls.items()}
    return out


def _channels(color):
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def contrast(a, b):
    def lum(color):
        r, g, bl = (c / 255 for c in _channels(color))
        r, g, bl = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, bl))
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def blend(rgba, bg):
    alpha = int(rgba[7:9], 16) / 255
    mixed = [round(f * alpha + b * (1 - alpha)) for f, b in zip(_channels(rgba), _channels(bg))]
    return "#" + "".join(f"{c:02X}" for c in mixed)


def test_nextorian_blocks_define_every_token():
    b = blocks()
    for sel in (NEXTORIAN_DARK, NEXTORIAN_LIGHT):
        assert set(TOKENS) <= set(b[sel]) and "color-scheme" in b[sel]
        assert "font" not in b[sel]


def test_nextorian_keeps_todays_values():
    dark, light = blocks()[NEXTORIAN_DARK], blocks()[NEXTORIAN_LIGHT]
    assert dark["bg"] == "#1A1110" and dark["accent"] == "#C4005E" and dark["pill-active-bg"] == "#283A16"
    assert light["bg"] == "#F9F5F2" and light["accent"] == "#C4005E" and light["yellow"] == "#FECD40"
    assert light["switch-track-off"] == "#8C817D" and dark["switch-track-off"] == "#4A3B39"
    assert dark["banner-fg"] == light["banner-fg"] == "#1A1110"
    assert dark["term-bg"] == light["term-bg"] == "#0E0908" and dark["term-cursor"] == "#FF5AA5"
    assert dark["check-fg"] == light["check-fg"] == "#FFFFFF"


PRE_PAINT = """<script>
function applyStoredTheme() {
  var d = document.documentElement, t = null, p = null;
  try { t = localStorage.getItem("factory.theme"); p = localStorage.getItem("factory.palette"); } catch (e) {}
  if (t === "light") d.dataset.theme = "light"; else delete d.dataset.theme;
  if (["greyscale", "monochrome", "retropunk", "wachovsky"].indexOf(p) >= 0) d.dataset.palette = p; else delete d.dataset.palette;
}
applyStoredTheme();
</script>
<link rel="stylesheet" href="/static/themes.css">"""


def test_dashboard_applies_the_stored_theme_before_the_stylesheet():
    page = (WEB / "dashboard.html").read_text()
    head = page[:page.index("</head>")]
    assert PRE_PAINT in head and head.index(PRE_PAINT) < head.index("<style>")


def test_dashboard_has_no_inline_tokens_or_hard_coded_theme_colors():
    page = (WEB / "dashboard.html").read_text()
    assert ":root {" not in page and ':root[data-theme="light"]' not in page and "--bg:" not in page
    for rule in ["color: #FFFFFF", "color: #1A1110", "background: #FFFFFF", "border: solid #FFFFFF", "#0E0908", "#2E2322;"]:
        assert rule not in page.split("<style>")[1].split("</style>")[0], rule
    for text in ["color: var(--accent-fg)", "color: var(--banner-fg)", "background: var(--switch-knob-off)",
                 "background: var(--switch-track-off)", "background: var(--switch-knob-on)", "border: solid var(--check-fg)",
                 "background: var(--term-bg)", "var(--pill-active-bg)", "var(--pill-wait-fg)", "theme: liveTheme()"]:
        assert text in page, text
    assert "const LIVE_THEME" not in page


def test_editor_applies_the_stored_theme_before_the_stylesheet():
    page = (WEB / "editor.html").read_text()
    head = page[:page.index("</head>")]
    assert PRE_PAINT in head and head.index(PRE_PAINT) < head.index("<style>")
    assert ":root {" not in page and "--bg:" not in page and "color: #FFFFFF" not in page
    assert "color: var(--accent-fg)" in page


def test_editor_follows_theme_changes_from_other_tabs():
    page = (WEB / "editor.html").read_text()
    assert 'window.addEventListener("storage", (e) => { if (e.key === THEME_KEY || e.key === "factory.palette") { applyStoredTheme(); themeLabel(); } });' in page

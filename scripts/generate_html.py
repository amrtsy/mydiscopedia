"""
Generates docs/index.html and docs/performers/{slug}.html from
docs/data/manifest.json (produced by build.py).

Run this AFTER build.py.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
PERFORMERS_DIR = ROOT / "docs" / "performers"

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;'
    '9..144,600&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:'
    'wght@400;500&display=swap" rel="stylesheet">'
)

PERFORMER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>{name} — Discography</title>
{fonts}
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>

<header>
  <div class="eyebrow">Discography</div>
  <h1>{name}</h1>
  <div class="sub">{year_range} &middot; {count} recordings</div>
  <a class="back-link" href="../index.html">&larr; All performers</a>
</header>

<div class="toolbar">
  <div class="field">
    <label for="f-composer">Composer</label>
    <select id="f-composer"><option value="">All</option></select>
  </div>
  <div class="field">
    <label for="f-label">Label</label>
    <select id="f-label"><option value="">All</option></select>
  </div>
  <div class="field">
    <label for="f-live">Type</label>
    <select id="f-live">
      <option value="">All</option>
      <option value="live">Live</option>
      <option value="studio">Studio</option>
    </select>
  </div>
  <div class="field">
    <label for="f-sort">Sort by</label>
    <select id="f-sort">
      <option value="composer">Composer / work</option>
      <option value="count">Most recorded works first</option>
    </select>
  </div>
  <div class="field">
    <label for="f-search">Search (work, performers, notes)</label>
    <input type="text" id="f-search" placeholder="e.g. Elgar, Barenboim">
  </div>
  <div class="count" id="count"></div>
</div>

<div class="list" id="list"></div>

<script>
  window.DISCOGRAPHY_CONFIG = {{ dataUrl: '../data/{slug}.json' }};
</script>
<script src="../assets/discography.js"></script>

</body>
</html>
"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>MyDiscopedia</title>
{fonts}
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

<header>
  <div class="eyebrow">MyDiscopedia</div>
  <h1>20th-Century String Virtuosi</h1>
  <div class="sub">A discography reference for violin &amp; cello recordings</div>
</header>

<div class="performer-grid">
{cards}
</div>

</body>
</html>
"""

CARD_TEMPLATE = """  <a class="performer-card" href="performers/{slug}.html">
    <div class="name">{name}</div>
    <div class="meta">{year_range} &middot; {count} recordings</div>
  </a>"""


def main():
    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    PERFORMERS_DIR.mkdir(parents=True, exist_ok=True)

    cards = []
    for entry in manifest:
        html = PERFORMER_TEMPLATE.format(fonts=FONTS_LINK, **entry)
        out = PERFORMERS_DIR / f"{entry['slug']}.html"
        out.write_text(html, encoding="utf-8")
        cards.append(CARD_TEMPLATE.format(**entry))
        print(f"wrote {out.relative_to(ROOT)}")

    index_html = INDEX_TEMPLATE.format(fonts=FONTS_LINK, cards="\n".join(cards))
    (ROOT / "docs" / "index.html").write_text(index_html, encoding="utf-8")
    print(f"wrote docs/index.html")


if __name__ == "__main__":
    main()

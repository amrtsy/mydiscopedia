"""
Generates docs/index.html, docs/about.html, docs/contact.html and
docs/performers/{slug}.html from docs/data/manifest.json (produced by
build.py).

Run this AFTER build.py.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
PERFORMERS_DIR = ROOT / "docs" / "performers"

CONTACT_EMAIL = "dasmagischend@gmail.com"

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;'
    '9..144,600&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:'
    'wght@400;500&display=swap" rel="stylesheet">'
)


def site_nav(base, active):
    """base: '' for top-level pages, '../' for pages under performers/."""
    def link(href, label, key):
        cls = ' class="active"' if key == active else ''
        return f'<a href="{base}{href}"{cls}>{label}</a>'
    return f"""<nav class="site-nav">
  <div class="site-nav-inner">
    <a class="site-nav-brand" href="{base}index.html">MyDiscopedia</a>
    <div class="site-nav-links">
      {link('index.html', 'Home', 'home')}
      {link('about.html', 'About', 'about')}
      {link('contact.html', 'Contact', 'contact')}
    </div>
  </div>
</nav>"""


def site_footer(base):
    return f"""<footer class="site-footer">
  <div class="site-footer-links">
    <a href="{base}index.html">Home</a>
    <a href="{base}about.html">About</a>
    <a href="{base}contact.html">Contact</a>
  </div>
  <div class="site-footer-copyright">
    Copyright &copy; <span class="copyright-year"></span> MyDiscopedia. All rights reserved.
  </div>
</footer>
<script>
  document.querySelectorAll('.copyright-year').forEach(function(el){{
    el.textContent = new Date().getFullYear();
  }});
</script>"""


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

{nav}

<header>
  <div class="eyebrow">Discography</div>
  <h1>{name}</h1>
  <div class="sub">{year_range} &middot; {count} recordings</div>
  <a class="back-link" href="../index.html">&larr; All performers</a>
</header>

<div class="toolbar">
  <button type="button" class="menu-toggle" id="menu-toggle" aria-expanded="false" aria-controls="toolbar-fields">&#9776; Filters</button>
  <div class="toolbar-fields" id="toolbar-fields">
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
        <option value="date">Recording date</option>
      </select>
    </div>
    <div class="field">
      <label for="f-search">Search (work, performers, notes)</label>
      <input type="text" id="f-search" placeholder="e.g. Elgar, Barenboim">
    </div>
  </div>
  <div class="count" id="count"></div>
</div>

<div class="list" id="list"></div>

{footer}

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

{nav}

<header>
  <div class="eyebrow">MyDiscopedia</div>
  <h1>20th-Century String Virtuosi</h1>
  <div class="sub">A discography reference for violin &amp; cello recordings</div>
</header>

<div class="performer-grid">
{cards}
</div>

{footer}

</body>
</html>
"""

CARD_TEMPLATE = """  <a class="performer-card" href="performers/{slug}.html">
    <div class="name">{name}</div>
    <div class="meta">{year_range} &middot; {count} recordings</div>
  </a>"""

ABOUT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>About — MyDiscopedia</title>
{fonts}
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

{nav}

<header>
  <div class="eyebrow">MyDiscopedia</div>
  <h1>About</h1>
</header>

<div class="page-content">
  <p>More information coming soon.</p>
</div>

{footer}

</body>
</html>
"""

CONTACT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>Contact — MyDiscopedia</title>
{fonts}
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

{nav}

<header>
  <div class="eyebrow">MyDiscopedia</div>
  <h1>Contact</h1>
</header>

<div class="page-content">
  <p>Questions, corrections, or additions to the discography? Get in touch:</p>
  <p><a class="contact-email" href="mailto:{email}">{email}</a></p>
</div>

{footer}

</body>
</html>
"""


def main():
    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    PERFORMERS_DIR.mkdir(parents=True, exist_ok=True)

    cards = []
    for entry in manifest:
        html = PERFORMER_TEMPLATE.format(
            fonts=FONTS_LINK,
            nav=site_nav("../", None),
            footer=site_footer("../"),
            **entry,
        )
        out = PERFORMERS_DIR / f"{entry['slug']}.html"
        out.write_text(html, encoding="utf-8")
        cards.append(CARD_TEMPLATE.format(**entry))
        print(f"wrote {out.relative_to(ROOT)}")

    index_html = INDEX_TEMPLATE.format(
        fonts=FONTS_LINK,
        nav=site_nav("", "home"),
        footer=site_footer(""),
        cards="\n".join(cards),
    )
    (ROOT / "docs" / "index.html").write_text(index_html, encoding="utf-8")
    print("wrote docs/index.html")

    about_html = ABOUT_TEMPLATE.format(
        fonts=FONTS_LINK, nav=site_nav("", "about"), footer=site_footer("")
    )
    (ROOT / "docs" / "about.html").write_text(about_html, encoding="utf-8")
    print("wrote docs/about.html")

    contact_html = CONTACT_TEMPLATE.format(
        fonts=FONTS_LINK, nav=site_nav("", "contact"), footer=site_footer(""),
        email=CONTACT_EMAIL,
    )
    (ROOT / "docs" / "contact.html").write_text(contact_html, encoding="utf-8")
    print("wrote docs/contact.html")


if __name__ == "__main__":
    main()

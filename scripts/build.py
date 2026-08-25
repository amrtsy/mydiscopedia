"""
MyDiscopedia build script
--------------------------
Reads performer sheets from the source spreadsheet and converts them into
per-performer JSON files under docs/data/, ready for the static site.

USAGE (local xlsx, for development):
    python3 build.py --xlsx path/to/MyDiscopedia.xlsx

USAGE (published Google Sheet CSVs, for production / GitHub Actions):
    python3 build.py --csv-base "https://docs.google.com/spreadsheets/d/XXXX/gviz/tq?tqx=out:csv&sheet="

Rows where Composer or Work is blank are skipped (e.g. broadcast records with
unknown repertoire) — by design, per project policy.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import urllib.request
    import csv
    import io
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_OUT = ROOT / "docs" / "data"

# slug: display name shown on site
PERFORMERS = {
    "stern": "Isaac Stern",
    "szeryng": "Henryk Szeryng",
    "menuhin": "Yehudi Menuhin",
    "grumiaux": "Arthur Grumiaux",
    "oistrakh": "David Oistrakh",
    "francescatti": "Zino Francescatti",
    "rabin": "Michael Rabin",
    "du-pre": "Jacqueline du Pré",
}

# maps slug -> actual sheet name in the spreadsheet (only needed where they differ)
SHEET_NAMES = {
    "du-pre": "Du Pre",
}

COLS = ["composer", "composer_id", "work", "date", "accompanists",
        "orchestra", "location", "label", "notes", "reference"]


# ---------- parsing helpers (shared across all performers) ----------

def parse_date(raw):
    if raw is None or raw == "":
        return {"display": None, "sort": "9999-99-99"}
    if isinstance(raw, datetime.datetime):
        return {"display": raw.strftime("%Y/%m/%d"), "sort": raw.strftime("%Y-%m-%d")}
    if isinstance(raw, float) or isinstance(raw, int):
        y = int(raw)
        return {"display": str(y), "sort": f"{y:04d}-01-01"}
    if isinstance(raw, str):
        m = re.match(r"(\d{4})(?:/(\d{1,2}))?(?:/(\d{1,2}))?", raw)
        if m:
            y, mo, d = m.group(1), m.group(2) or "01", m.group(3) or "01"
            mo = mo.zfill(2)[:2]
            d = re.sub(r"\D.*", "", d).zfill(2)[:2] or "01"
            return {"display": raw, "sort": f"{y}-{mo}-{d}"}
        return {"display": raw, "sort": "9999-99-99"}
    return {"display": str(raw), "sort": "9999-99-99"}


def parse_people(raw):
    if not raw:
        return []
    parts = re.findall(r'"([^"]+)"', raw)
    if not parts:
        parts = [raw]
    people = []
    for p in parts:
        m = re.match(r"(.+?)\(([^)]+)\)\s*$", p.strip())
        if m:
            people.append({"name": m.group(1).strip(), "role": m.group(2).strip()})
        else:
            people.append({"name": p.strip(), "role": None})
    return people


def parse_labels(raw):
    if not raw:
        return []
    return [l.strip() for l in raw.split(",") if l.strip()]


def build_works_index(rows):
    """Build a lookup from the Works master sheet:
    (composer_id, "title+opus" text) -> {category_id, sort_key}

    category_id: 1 = chamber/solo work, 2 = orchestral work (per project
    convention). sort_key: manually-assigned ordering number (float), or
    None if not yet assigned.

    Only rows with a work_id (i.e. "linked"/complete master rows) are
    indexed; the rest are treated as not-yet-classified.
    """
    index = {}
    for r in rows:
        # work_id, composer_id, name, title, opus_number, title+opus, type,
        # sort_key, arranger_id, parent_work_id, category_id
        if len(r) < 11 or r[0] in (None, ""):
            continue
        composer_id, title_opus, sort_key_raw, category_id = r[1], r[5], r[7], r[10]
        if composer_id is None or not title_opus:
            continue
        try:
            sort_key = float(sort_key_raw) if sort_key_raw not in (None, "") else None
        except (TypeError, ValueError):
            sort_key = None
        try:
            category_id = int(category_id) if category_id not in (None, "") else None
        except (TypeError, ValueError):
            category_id = None
        key = (str(composer_id).strip(), str(title_opus).strip())
        index[key] = {"category_id": category_id, "sort_key": sort_key}
    return index


def build_records(rows, works_index=None):
    works_index = works_index or {}
    records = []
    rid = 1
    skipped = 0
    unmatched = []
    for r in rows:
        composer, composer_id, work, date_raw, accomp, orch, loc, label, notes, ref = (
            list(r) + [None] * (10 - len(r))
        )[:10]
        # Policy: skip rows with no composer or no work (e.g. broadcast
        # records where the repertoire is unknown).
        if not composer or not work:
            skipped += 1
            continue
        d = parse_date(date_raw)
        notes_str = str(notes) if notes else None
        work_str = str(work).strip()
        lookup_key = (str(composer_id).strip() if composer_id is not None else "", work_str)
        match = works_index.get(lookup_key)
        if match is None:
            unmatched.append(f"{composer} — {work_str}")
        rec = {
            "id": rid,
            "composer": str(composer).strip(),
            "composer_id": composer_id,
            "work": work_str,
            "date_display": d["display"],
            "date_sort": d["sort"],
            "accompanists": parse_people(accomp),
            "orchestra": orch,
            "location": loc,
            "labels": parse_labels(label),
            "is_live": bool(notes_str and "live" in notes_str.lower()),
            "notes": notes_str,
            "reference": ref,
            "category_id": match["category_id"] if match else None,
            "sort_key": match["sort_key"] if match else None,
        }
        records.append(rec)
        rid += 1
    records.sort(key=lambda x: x["date_sort"])
    return records, skipped, unmatched


def build_references(rows):
    """Convert References sheet rows (Category, SiteName, URL, Description)
    into a list grouped by category, in first-seen category order."""
    order = []
    grouped = {}
    skipped = 0
    for r in rows:
        category, site_name, url, description = (list(r) + [None] * (4 - len(r)))[:4]
        if not category or not site_name or not url:
            skipped += 1
            continue
        category = str(category).strip()
        if category not in grouped:
            grouped[category] = []
            order.append(category)
        grouped[category].append({
            "site_name": str(site_name).strip(),
            "url": str(url).strip(),
            "description": str(description).strip() if description else None,
        })
    result = [{"category": c, "sites": grouped[c]} for c in order]
    return result, skipped


# ---------- data sources ----------

def rows_from_xlsx(xlsx_path, sheet_name):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[sheet_name]
    return list(ws.iter_rows(min_row=2, values_only=True))


def rows_from_csv_url(url):
    with urllib.request.urlopen(url) as resp:
        text = resp.read().decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)[1:]  # skip header
    return rows


def rows_from_csv_export(sheet_id, gid):
    """Fetch a single sheet tab as raw CSV via the classic export endpoint.

    Unlike /gviz/tq?tqx=out:csv (which infers a type per column and blanks
    out any cell that doesn't match — e.g. a "1962/06" partial date in an
    otherwise full-date column), this endpoint returns each cell's literal
    text/display value, which matches what's actually typed in the sheet.
    """
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return rows_from_csv_url(url)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", help="Path to local MyDiscopedia.xlsx (dev mode)")
    ap.add_argument("--sheet-id", help="Google Sheet file ID (prod mode). "
                     "Used with --gids to fetch each tab's raw CSV export.")
    ap.add_argument("--gids", help="Path to a JSON file mapping slug -> gid "
                     "(prod mode), e.g. scripts/gids.json")
    ap.add_argument("--csv-base", help="[DEPRECATED] Base URL for /gviz/tq "
                     "CSV export. Prefer --sheet-id/--gids instead: gviz "
                     "blanks out cells that don't match the column's "
                     "inferred type (e.g. partial dates like '1962/06').")
    ap.add_argument("--only", help="Comma-separated slugs to build (default: all)")
    args = ap.parse_args()

    if not args.xlsx and not args.csv_base and not (args.sheet_id and args.gids):
        sys.exit("Specify --xlsx (dev), or --sheet-id + --gids (prod)")

    DATA_OUT.mkdir(parents=True, exist_ok=True)

    targets = args.only.split(",") if args.only else list(PERFORMERS.keys())

    gid_map = {}
    if args.gids:
        gid_map = json.loads(Path(args.gids).read_text(encoding="utf-8"))

    # --- Works master (composer_id + title+opus -> category_id, sort_key) ---
    if args.xlsx:
        works_rows = rows_from_xlsx(args.xlsx, "Works")
    elif args.sheet_id and args.gids:
        if "works" not in gid_map:
            sys.exit(f"No gid configured for 'works' in {args.gids}")
        works_rows = rows_from_csv_export(args.sheet_id, gid_map["works"])
    else:
        import urllib.parse
        url = args.csv_base + urllib.parse.quote("Works")
        works_rows = rows_from_csv_url(url)
    works_index = build_works_index(works_rows)
    print(f"[works master  ] {len(works_index):5d} classified works loaded "
          f"(category_id + sort_key)")

    summary = []
    all_unmatched = {}
    for slug in targets:
        display_name = PERFORMERS[slug]
        sheet_name = SHEET_NAMES.get(slug, _default_sheet_name(slug))

        if args.xlsx:
            rows = rows_from_xlsx(args.xlsx, sheet_name)
        elif args.sheet_id and args.gids:
            if slug not in gid_map:
                sys.exit(f"No gid configured for '{slug}' in {args.gids}")
            rows = rows_from_csv_export(args.sheet_id, gid_map[slug])
        else:
            import urllib.parse
            url = args.csv_base + urllib.parse.quote(sheet_name)
            rows = rows_from_csv_url(url)

        records, skipped, unmatched = build_records(rows, works_index)
        if unmatched:
            all_unmatched[slug] = unmatched

        out_path = DATA_OUT / f"{slug}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        years = [r["date_sort"][:4] for r in records if r["date_sort"] != "9999-99-99"]
        year_range = f"{min(years)}\u2013{max(years)}" if years else "n/a"

        summary.append({
            "slug": slug, "name": display_name, "count": len(records),
            "skipped": skipped, "year_range": year_range,
        })
        print(f"[{slug:14s}] {len(records):5d} records written  "
              f"(skipped {skipped} incomplete rows, {len(unmatched)} not "
              f"found in Works master)  years {year_range}")

    # write a manifest the index page can use
    with open(DATA_OUT / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # --- References sheet (not a performer; always built) ---
    if args.xlsx:
        ref_rows = rows_from_xlsx(args.xlsx, "References")
    elif args.sheet_id and args.gids:
        if "references" not in gid_map:
            sys.exit(f"No gid configured for 'references' in {args.gids}")
        ref_rows = rows_from_csv_export(args.sheet_id, gid_map["references"])
    else:
        import urllib.parse
        url = args.csv_base + urllib.parse.quote("References")
        ref_rows = rows_from_csv_url(url)

    references, ref_skipped = build_references(ref_rows)
    with open(DATA_OUT / "references.json", "w", encoding="utf-8") as f:
        json.dump(references, f, ensure_ascii=False, indent=2)
    total_refs = sum(len(c["sites"]) for c in references)
    print(f"[references     ] {total_refs:5d} entries written  "
          f"(skipped {ref_skipped} incomplete rows)  categories {len(references)}")

    # --- Diagnostics: works that couldn't be matched to the Works master ---
    # These fall back to "uncategorized" (sorted alphabetically, after the
    # chamber/orchestral groups) instead of failing the build.
    unmatched_path = ROOT / "scripts" / "unmatched_works.txt"
    total_unmatched = sum(len(v) for v in all_unmatched.values())
    if all_unmatched:
        lines = [f"# {total_unmatched} work(s) not found in the Works master "
                 f"(category_id/sort_key unavailable — sorted alphabetically "
                 f"as 'uncategorized' instead)\n"]
        for slug, items in all_unmatched.items():
            lines.append(f"\n## {slug} ({len(items)})")
            lines.extend(f"- {item}" for item in sorted(set(items)))
        unmatched_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"[diagnostics    ] {total_unmatched:5d} unmatched works written to "
              f"scripts/unmatched_works.txt")
    elif unmatched_path.exists():
        unmatched_path.unlink()


def _default_sheet_name(slug):
    # slug "du-pre" -> "Du Pre" already in SHEET_NAMES; everything else is
    # just the Title-Case display name's surname portion == the sheet tab name
    return PERFORMERS[slug].split()[-1] if slug not in SHEET_NAMES else SHEET_NAMES[slug]


if __name__ == "__main__":
    main()

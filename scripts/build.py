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


def build_records(rows):
    records = []
    rid = 1
    skipped = 0
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
        rec = {
            "id": rid,
            "composer": str(composer).strip(),
            "composer_id": composer_id,
            "work": str(work).strip(),
            "date_display": d["display"],
            "date_sort": d["sort"],
            "accompanists": parse_people(accomp),
            "orchestra": orch,
            "location": loc,
            "labels": parse_labels(label),
            "is_live": bool(notes_str and "live" in notes_str.lower()),
            "notes": notes_str,
            "reference": ref,
        }
        records.append(rec)
        rid += 1
    records.sort(key=lambda x: x["date_sort"])
    return records, skipped


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

    summary = []
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

        records, skipped = build_records(rows)

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
              f"(skipped {skipped} incomplete rows)  years {year_range}")

    # write a manifest the index page can use
    with open(DATA_OUT / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def _default_sheet_name(slug):
    # slug "du-pre" -> "Du Pre" already in SHEET_NAMES; everything else is
    # just the Title-Case display name's surname portion == the sheet tab name
    return PERFORMERS[slug].split()[-1] if slug not in SHEET_NAMES else SHEET_NAMES[slug]


if __name__ == "__main__":
    main()

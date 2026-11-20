"""Generate the glc_fcs30d collection: year and band catalogs, items, and their READMEs.

usage: python3 tools/build_stac.py

Deterministic from committed inputs, so CI regenerates the tree and diffs it:
  data/cogs.jsonl            one line per uploaded COG, written by tools/pipeline.py
  data/zenodo-record.json    the pinned upstream record (source assets, provenance)
  data/derived-assets.json   file fields of items.parquet, the overview and the thumbnail
The item tree (catalog/glc_fcs30d/<year>/) is gitignored; collection.json is committed.
"""
import json, os, re, shutil, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from classes import CLASSES, FILL_VALUES, NODATA

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CID = "glc_fcs30d"
OUT = f"{REPO}/catalog/{CID}"
PUBLIC = "https://data.source.coop/portolan-mirrors/glc-fcs30d"
REPO_URL = "https://github.com/nlebovits/glc-fcs30d"
COG = "image/tiff; application=geotiff; profile=cloud-optimized"
EXT = {
    "portolan": "https://schemas.portolan-sdi.org/portolan/v0.3.0/schema.json",
    "file": "https://stac-extensions.github.io/file/v2.1.0/schema.json",
    "proj": "https://stac-extensions.github.io/projection/v2.0.0/schema.json",
    "class": "https://stac-extensions.github.io/classification/v2.0.0/schema.json",
    "sci": "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
}
J, GJ, MD = "application/json", "application/geo+json", "text/markdown"
DOI, PAPER_DOI = "10.5281/zenodo.15063683", "10.5194/essd-16-1353-2024"
# verbatim from the user guide's Citations section, spacing normalized
CITATION = ("Zhang, X., Zhao, T., Xu, H., Liu, W., Wang, J., Chen, X., & Liu, L., 2024. GLC_FCS30D: The first global "
            "30-m land-cover dynamic monitoring product with a fine classification system from 1985 to 2022 using "
            "dense time-series Landsat imagery and continuous change-detection method. Earth Syst. Sci. Data, 16, "
            "1353–1381, https://doi.org/10.5194/essd-16-1353-2024.")


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"\(.*?\)", "", title).lower()).strip("-")


def class_list():
    out = [{"value": NODATA, "name": "no-data", "title": "No data (filled value)", "color_hint": "000000", "nodata": True}]
    for v in FILL_VALUES:
        if v != NODATA:
            out.append({"value": v, "name": "filled-value", "title": "Filled value", "color_hint": "FFFFFF"})
    for v, (title, rgb) in CLASSES.items():
        out.append({"value": v, "name": slug(title), "title": title, "color_hint": "%02X%02X%02X" % rgb})
    out.sort(key=lambda c: c["value"])
    assert len({c["name"] for c in out}) == len(out), "class names must be unique"
    return out


CLASS_LIST = class_list()


def lon_label(x):
    return f"{abs(x):g}°{'E' if x >= 0 else 'W'}" if x else "0°"


def lat_label(y):
    return f"{abs(y):g}°{'N' if y >= 0 else 'S'}" if y else "0°"


def tile_origin(tile):
    m = re.fullmatch(r"([EW])(\d+)([NS])(\d+)", tile)
    return (int(m[2]) * (1 if m[1] == "E" else -1), int(m[4]) * (1 if m[3] == "N" else -1))


def clamp_bbox(b):
    # tiles span 5.0003°, so the outer edges pass ±180 at the antimeridian
    return [round(max(-180.0, b[0]), 9), round(max(-90.0, b[1]), 9), round(min(180.0, b[2]), 9), round(min(90.0, b[3]), 9)]


def nav_links(rel_root, path):
    """Root, docs, browser, repository and hosting links that every catalog and the collection carry."""
    return [
        {"rel": "root", "href": rel_root, "type": J},
        {"rel": "describedby", "href": "./README.md", "type": MD, "title": "README"},
        {"rel": "agents", "href": "./AGENTS.md", "type": MD, "title": "Agent guide"},
        {"rel": "alternate", "href": f"https://browser.portolan-sdi.org/#/external/data.source.coop/portolan-mirrors/glc-fcs30d/{path}",
         "type": "text/html", "title": "Open in the data browser"},
        {"rel": "vcs", "href": REPO_URL, "type": "text/html", "title": "Source repository"},
        {"rel": "issues", "href": f"{REPO_URL}/issues", "type": "text/html", "title": "Report a problem"},
        {"rel": "about", "href": "https://source.coop/portolan-mirrors/glc-fcs30d", "type": "text/html",
         "title": "Hosting page on Source Cooperative"},
    ]


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")


def period(year):
    return f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z"


def band_index(year):
    return [1985, 1990, 1995].index(year) + 1 if year < 2000 else year - 1999


def item(c, band):
    year, tile = c["year"], c["tile"]
    iid = f"{year}-{tile}"
    x, y = tile_origin(tile)
    bbox = clamp_bbox(c["bbox"])
    gt = c["transform"]
    start, end = period(year)
    title = f"{tile} ({lon_label(x)} to {lon_label(x + 5)}, {lat_label(y - 5)} to {lat_label(y)}), {year}"
    s = c["stats"]
    return iid, {
        "type": "Feature", "stac_version": "1.1.0",
        "stac_extensions": [EXT["file"], EXT["proj"], EXT["class"]],
        "id": iid, "collection": CID,
        "geometry": {"type": "Polygon", "coordinates": [[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]]]},
        "bbox": bbox,
        "properties": {"title": title, "datetime": None, "start_datetime": start, "end_datetime": end},
        "assets": {"data": {
            # absolute, so items.parquet rows resolve on their own
            "href": f"{PUBLIC}/{CID}/{year}/{band}/{iid}/{iid}.tif", "type": COG, "title": f"Land cover {year}, tile {tile} (COG)", "roles": ["data"],
            "description": f"Class value of each 30 m pixel in {year}, with the class colors in an embedded color table. Converted without change from band {band_index(year)} of {os.path.basename(c['source_member'])}.",
            "nodata": NODATA, "data_type": "uint8",
            "statistics": {"minimum": s["MINIMUM"], "maximum": s["MAXIMUM"], "mean": round(s["MEAN"], 4),
                           "stddev": round(s["STDDEV"], 4), "valid_percent": round(s["VALID_PERCENT"], 4)},
            "proj:code": "EPSG:4326", "proj:shape": c["shape"], "proj:transform": [gt[1], gt[2], gt[0], gt[4], gt[5], gt[3]],
            "classification:classes": CLASS_LIST,
            "file:size": c["size"], "file:checksum": c["checksum"],
        }},
        "links": [
            {"rel": "root", "href": "../../../../catalog.json", "type": J},
            {"rel": "parent", "href": "../catalog.json", "type": J},
            {"rel": "collection", "href": "../../../collection.json", "type": J},
        ],
    }


BAND_README = """# GLC_FCS30D {year}, {west} to {east}

The {year} land cover map for the {n} tiles of 5° by 5° between {west} and {east}. Each tile is one STAC item with one Cloud Optimized GeoTIFF (COG) of 30 m class values.

| Tile | Covers | Item | COG |
|---|---|---|---|
{rows}

Open one tile without a download:

```sh
gdalinfo /vsicurl/{public}/{CID}/{year}/{band}/{first}/{first}.tif
```

The class values, titles and colors are in the [collection]({up}collection.json) and in the color table of each COG. See the [collection README]({up}README.md) for what the classes mean and the known issues.
"""

BAND_AGENTS = """# Agent guide: GLC_FCS30D {year}, {west} to {east}

- This catalog holds {n} items. Each item has one asset, `data`: a single-band uint8 COG of class values in EPSG:4326, nodata 0.
- The COG URL is `{public}/{CID}/{year}/{band}/<item id>/<item id>.tif`. The item id is `{year}-<tile>`, and the tile name is the upper-left corner of the tile.
- To search every year and tile at once, query `{public}/{CID}/items.parquet` with DuckDB instead of walking the catalogs.
- The class table is `classification:classes` on the data asset. Read the [collection agent guide]({up}AGENTS.md) before you compute areas.
"""

YEAR_README = """# GLC_FCS30D {year}

The {year} land cover map of the world at 30 m, as {n} tiles of 5° by 5°. The tiles are grouped in {nb} longitude bands of 10°, the same grouping as the source ZIP files.{five}

| Band | Tiles |
|---|---|
{rows}

See the [collection README](../README.md) for the classes, how the data was made, and the known issues.
"""

YEAR_AGENTS = """# Agent guide: GLC_FCS30D {year}

- This catalog holds {nb} band catalogs and {n} items, one for each 5° tile. Each item has one single-band uint8 COG of class values in EPSG:4326, nodata 0.
- To find the tiles for a place, query `{public}/{CID}/items.parquet` with DuckDB and filter on `bbox` and `start_datetime`, instead of walking these catalogs.
- Read the [collection agent guide](../AGENTS.md) before you compute areas or compare years.
"""

FIVE = (" The maps for 1985, 1990 and 1995 come from the 5-year files of the source, whose names say 19852000. "
        "The source has no maps for 1986–1989, 1991–1994 or 1996–1999.")


def main():
    rec = json.load(open(f"{REPO}/data/zenodo-record.json"))
    derived = json.load(open(f"{REPO}/data/derived-assets.json"))
    cogs = [json.loads(l) for l in open(f"{REPO}/data/cogs.jsonl")]
    assert len({(c["year"], c["tile"]) for c in cogs}) == len(cogs), "duplicate COG lines"
    by_year = defaultdict(lambda: defaultdict(list))
    for c in cogs:
        by_year[c["year"]][c["band"]].append(c)

    for d in os.listdir(OUT) if os.path.isdir(OUT) else []:
        if d.isdigit():
            shutil.rmtree(f"{OUT}/{d}")

    def band_bounds(band):
        # "W165-W170" holds tile columns W165 and W170, whose names are their west edges
        xs = [int(v[1:]) * (1 if v[0] == "E" else -1) for v in band.split("-")]
        return min(xs), max(xs) + 5

    year_links, all_bboxes = [], []
    for year in sorted(by_year):
        bands = by_year[year]
        border = sorted(bands, key=lambda b: band_bounds(b)[0])
        band_links, year_rows, n_year = [], [], 0
        for band in border:
            cs = sorted(bands[band], key=lambda c: (-tile_origin(c["tile"])[1], tile_origin(c["tile"])[0]))
            w, e = map(lon_label, band_bounds(band))
            bdir = f"{OUT}/{year}/{band}"
            links, rows = [], []
            for c in cs:
                iid, it = item(c, band)
                write(f"{bdir}/{iid}/{iid}.json", it)
                all_bboxes.append(it["bbox"])
                links.append({"rel": "item", "href": f"./{iid}/{iid}.json", "type": GJ, "title": it["properties"]["title"]})
                x, y = tile_origin(c["tile"])
                rows.append(f"| {c['tile']} | {lon_label(x)} to {lon_label(x + 5)}, {lat_label(y - 5)} to {lat_label(y)} "
                            f"| [{iid}](./{iid}/{iid}.json) | [{iid}.tif]({PUBLIC}/{CID}/{year}/{band}/{iid}/{iid}.tif) |")
            path = f"{CID}/{year}/{band}/catalog.json"
            write(f"{bdir}/catalog.json", {
                "type": "Catalog", "stac_version": "1.1.0", "stac_extensions": [EXT["portolan"]],
                "id": f"{CID}-{year}-{band}", "title": f"{year}, {w} to {e}",
                "description": f"The {year} land cover map for the {len(cs)} tiles of 5° by 5° between {w} and {e}, one item per tile.",
                "links": [nav_links("../../../catalog.json", path)[0], {"rel": "parent", "href": "../catalog.json", "type": J},
                          *nav_links("../../../catalog.json", path)[1:], *links]})
            fmt = dict(year=year, west=w, east=e, n=len(cs), band=band, public=PUBLIC, CID=CID, first=f"{year}-{cs[0]['tile']}", up="../../")
            write(f"{bdir}/README.md", BAND_README.format(rows="\n".join(rows), **fmt))
            write(f"{bdir}/AGENTS.md", BAND_AGENTS.format(**fmt))
            band_links.append({"rel": "child", "href": f"./{band}/catalog.json", "type": J, "title": f"{year}, {w} to {e}"})
            year_rows.append(f"| [{w} to {e}](./{band}/README.md) | {len(cs)} |")
            n_year += len(cs)
        path = f"{CID}/{year}/catalog.json"
        write(f"{OUT}/{year}/catalog.json", {
            "type": "Catalog", "stac_version": "1.1.0", "stac_extensions": [EXT["portolan"]],
            "id": f"{CID}-{year}", "title": f"Land cover {year}",
            "description": f"The {year} GLC_FCS30D land cover map of the world at 30 m: {n_year} tiles of 5° by 5° in {len(border)} longitude bands.",
            "links": [nav_links("../../catalog.json", path)[0], {"rel": "parent", "href": "../collection.json", "type": J},
                      *nav_links("../../catalog.json", path)[1:], *band_links]})
        fmt = dict(year=year, n=n_year, nb=len(border), public=PUBLIC, CID=CID, five=FIVE if year < 2000 else "")
        write(f"{OUT}/{year}/README.md", YEAR_README.format(rows="\n".join(year_rows), **fmt))
        write(f"{OUT}/{year}/AGENTS.md", YEAR_AGENTS.format(**fmt))
        year_links.append({"rel": "child", "href": f"./{year}/catalog.json", "type": J, "title": f"Land cover {year}"})

    bbox = [min(b[0] for b in all_bboxes), min(b[1] for b in all_bboxes), max(b[2] for b in all_bboxes), max(b[3] for b in all_bboxes)]
    years = sorted(by_year)
    files = {f["key"]: f for f in rec["files"]}
    assets = {}
    for key, d in derived.items():
        assets[key] = d
    for k in sorted(files):
        f = files[k]
        md5 = f["checksum"].removeprefix("md5:")
        base = {"href": f["links"]["self"], "file:size": f["size"], "file:checksum": "d50110" + md5}  # multihash: md5 code 0xd5 as varint, length 16
        m = re.search(r"maps_(.+)\.zip$", k)
        if m:
            assets[f"source-{m[1]}"] = {**base, "type": "application/zip", "roles": ["source"],
                                        "title": f"Source ZIP {m[1]} (GeoTIFFs, all years)",
                                        "description": f"The upstream ZIP of the GeoTIFFs for the tiles in band {m[1]}: one 3-band file for 1985, 1990 and 1995 and one 23-band file for 2000–2022 per tile."}
        elif k.endswith(".pdf"):
            assets["user-guide"] = {**base, "type": "application/pdf", "roles": ["metadata"], "title": "GLC_FCS30D user guide (PDF)",
                                    "description": "The producer's user guide: the class table, the colors, the tile naming and the file layout."}
        elif k.endswith(".lyr"):
            assets["legend-lyr"] = {**base, "type": "application/octet-stream", "roles": ["metadata"], "title": "GLC_FCS30D legend (ArcGIS layer file)",
                                    "description": "The producer's ArcGIS legend for the class values. The COGs carry the same colors in their color tables."}
    assert sum(k.startswith("source-") for k in assets) == 36
    updated = max(c["fetched_at"] for c in cogs)
    path = f"{CID}/collection.json"
    nav = nav_links("../catalog.json", path)
    collection = {
        "type": "Collection", "stac_version": "1.1.0",
        "stac_extensions": [EXT["portolan"], EXT["file"], EXT["proj"], EXT["class"], EXT["sci"]],
        "id": CID,
        "title": "GLC_FCS30D global 30 m land cover, 1985–2022",
        "description": (
            "Global land cover at 30 m with 35 classes, from GLC_FCS30D v2 by the Aerospace Information Research Institute, "
            "Chinese Academy of Sciences. There is one map for each of 1985, 1990 and 1995, and one map for each year from 2000 to 2022. "
            f"Each map is {len({c['tile'] for c in cogs if c['year'] == years[-1]})} tiles of 5° by 5°, and each tile is one item with a "
            "single-band Cloud Optimized GeoTIFF of class values with an embedded color table. The items are grouped by year, "
            "then by 10° longitude band. Search them all at once with the items.parquet asset."),
        "keywords": ["land cover", "land use", "land cover change", "Landsat", "30 m", "global", "time series", "classification"],
        "license": "CC-BY-4.0",
        "providers": [
            {"name": "Aerospace Information Research Institute, Chinese Academy of Sciences",
             "description": "Produced GLC_FCS30D (Liangyun Liu, Xiao Zhang and Zhehua Li) and publishes it on Zenodo.",
             "roles": ["producer", "licensor"], "url": f"https://doi.org/{DOI}"},
            {"name": "Portolan Mirrors",
             "description": "Maintains this mirror: split each multi-year GeoTIFF into one COG per year and tile, and wrote the STAC metadata, item mirror and documentation.",
             "roles": ["processor", "host"], "url": REPO_URL},
        ],
        "extent": {"spatial": {"bbox": [bbox]},
                   "temporal": {"interval": [[period(years[0])[0], period(years[-1])[1]]]}},
        "item_assets": {"data": {
            "type": COG, "title": "Land cover (COG)", "roles": ["data"], "nodata": NODATA, "data_type": "uint8",
            "proj:code": "EPSG:4326", "classification:classes": CLASS_LIST}},
        "assets": dict(sorted(assets.items())),
        "sci:doi": PAPER_DOI, "sci:citation": CITATION,
        "updated": updated,
        "links": [
            nav[0], {"rel": "parent", "href": "../catalog.json", "type": J},
            {"rel": "license", "href": "https://creativecommons.org/licenses/by/4.0/", "type": "text/html",
             "title": "Creative Commons Attribution 4.0 International"},
            {"rel": "via", "href": f"https://doi.org/{DOI}", "type": "text/html", "title": "GLC_FCS30D v2 on Zenodo"},
            {"rel": "cite-as", "href": f"https://doi.org/{PAPER_DOI}", "type": "text/html", "title": "GLC_FCS30D paper (ESSD, 2024)"},
            *nav[1:], *year_links],
    }
    write(f"{OUT}/collection.json", collection)
    root_path = f"{REPO}/catalog/catalog.json"
    root = json.load(open(root_path))
    root["updated"] = updated  # a mirror records its last sync on the root too (PTL-PRO-003)
    write(root_path, root)
    print(f"{len(cogs)} items, {len(years)} years, {sum(len(b) for b in by_year.values())} band catalogs")


if __name__ == "__main__":
    main()

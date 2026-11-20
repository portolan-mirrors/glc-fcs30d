"""Write the stac-geoparquet item mirror, items.parquet, and record it in data/derived-assets.json.

usage: <python with stac-geoparquet, geoparquet-io and pyyaml> tools/items_parquet.py
       then python3 tools/build_stac.py, so collection.json carries the new size and checksum.
Writes <data_dir>/glc_fcs30d/items.parquet; tools/upload_data.py uploads it.

Same recipe as `portolan stac-geoparquet` (portolan_cli/stac_parquet.py): stac-geoparquet's arrow
conversion, rows in Hilbert order with geoparquet-io. Every item is read from the generated tree.
"""
import glob, hashlib, json, os, sys

import pyarrow.parquet as pq
import stac_geoparquet.arrow
from geoparquet_io.api.table import Table

sys.path.insert(0, os.path.dirname(__file__))
from publish import load_config

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COL = f"{REPO}/catalog/glc_fcs30d"
OUT = os.path.join(REPO, load_config()["data_dir"], "glc_fcs30d", "items.parquet")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

paths = sorted(glob.glob(f"{COL}/[0-9]*/*/*/*.json"))
items = [json.load(open(p)) for p in paths]
assert items and all(i["type"] == "Feature" for i in items)
table = stac_geoparquet.arrow.parse_stac_items_to_arrow(items).read_all()
ordered = Table(table, geometry_column="geometry").sort_hilbert().to_arrow()
ordered = ordered.replace_schema_metadata(table.schema.metadata)
stac_geoparquet.arrow.to_parquet(ordered, OUT)

meta = pq.ParquetFile(OUT).metadata
assert meta.num_rows == len(items) and all(meta.row_group(i).num_rows <= 150_000 for i in range(meta.num_row_groups))
sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()

p = f"{REPO}/data/derived-assets.json"
derived = json.load(open(p))
derived["geoparquet-items"] = {
    "href": "./items.parquet", "type": "application/vnd.apache.parquet", "roles": ["collection-mirror"],
    "title": "All items as stac-geoparquet",
    "description": f"A stac-geoparquet copy of the {len(items)} items of this collection, one row for each item, in Hilbert order of the item bbox.",
    "file:size": os.path.getsize(OUT), "file:checksum": "1220" + sha,
}
open(p, "w").write(json.dumps(derived, indent=2) + "\n")
print(f"{len(items)} rows in {meta.num_row_groups} row group(s), {os.path.getsize(OUT)} bytes")

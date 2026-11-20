"""Build the 2022 overview COG (8-bit RGBA, EPSG:3857) and the thumbnail from the published COGs.

usage: python3 tools/overview.py
Reads each 2022 tile's internal overviews over HTTP, so nothing is downloaded in full.
Writes <data_dir>/glc_fcs30d/overview-2022.tif (uploaded by tools/upload_data.py) and
catalog/glc_fcs30d/thumbnail.png (committed), and records both in data/derived-assets.json.
"""
import hashlib, json, math, os, shutil, sys
from multiprocessing import Pool

from osgeo import gdal

gdal.UseExceptions()
gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", "5")
gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")  # no .aux.xml sidecar next to the published thumbnail
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
from publish import load_config  # noqa: E402
PUBLIC = "https://data.source.coop/portolan-mirrors/glc-fcs30d"
YEAR = 2022
WORLD = 20037508.342789244
RES = WORLD * 2 / 16384  # 2.4 km, web map zoom 6
SOUTH, NORTH = -60, 80  # the tiles span 60°S to 80°N


def merc_y(lat):
    return 6378137 * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


# 3:2 thumbnail window: full width, from 60°S up to about 83.7°N
THUMB_Y = (merc_y(SOUTH), merc_y(SOUTH) + WORLD * 2 * 2 / 3)


def warp_tile(args):
    """One tile's 2022 map, mode-resampled from its internal overviews onto the overview grid."""
    url, dst = args
    gdal.Warp(dst, url, dstSRS="EPSG:3857", xRes=RES, yRes=RES, targetAlignedPixels=True, resampleAlg="mode",
              overviewLevel="AUTO", srcNodata=0, dstNodata=0, creationOptions=["COMPRESS=ZSTD"])
    return dst


def main():
    out = os.path.join(REPO, load_config()["data_dir"], "glc_fcs30d")
    os.makedirs(out, exist_ok=True)
    cogs = [json.loads(l) for l in open(f"{REPO}/data/cogs.jsonl")]
    urls = sorted(f"/vsicurl/{PUBLIC}/{c['key']}" for c in cogs if c["year"] == YEAR)
    print(len(urls), "tiles for", YEAR)
    # warp each tile on its own, in parallel processes: one sequential warp over 961 /vsicurl sources
    # spends most of its time on HTTP latency, and GDAL's multithreaded warp deadlocked on them
    parts = f"{out}/_parts"
    os.makedirs(parts, exist_ok=True)
    with Pool(32) as pool:
        locals_ = pool.map(warp_tile, [(u, f"{parts}/{i}.tif") for i, u in enumerate(urls)])
    warped = f"{out}/_{YEAR}-3857.tif"
    gdal.Warp(warped, locals_, dstSRS="EPSG:3857", xRes=RES, yRes=RES, outputBounds=(-WORLD, merc_y(SOUTH), WORLD, merc_y(NORTH)),
              resampleAlg="near", creationOptions=["TILED=YES", "COMPRESS=ZSTD"], srcNodata=0, dstNodata=0)
    rgba = gdal.Translate("", warped, format="VRT", rgbExpand="rgba")
    ov = f"{out}/overview-{YEAR}.tif"
    gdal.Translate(ov, rgba, format="COG", creationOptions=[
        "COMPRESS=ZSTD", "PREDICTOR=2", "BLOCKSIZE=512", "OVERVIEW_RESAMPLING=NEAREST", "NUM_THREADS=ALL_CPUS"])
    th = f"{REPO}/catalog/glc_fcs30d/thumbnail.png"
    gdal.Translate(th, ov, format="PNG", width=900, height=600, projWin=(-WORLD, THUMB_Y[1], WORLD, THUMB_Y[0]),
                   resampleAlg="nearest")
    os.remove(warped)
    shutil.rmtree(parts)

    def fields(p):
        return {"file:size": os.path.getsize(p), "file:checksum": "1220" + hashlib.sha256(open(p, "rb").read()).hexdigest()}

    d = json.load(open(f"{REPO}/data/derived-assets.json"))
    d["overview"] = {
        "href": f"./overview-{YEAR}.tif", "type": "image/tiff; application=geotiff; profile=cloud-optimized",
        "roles": ["visual", "overview"], "title": f"Land cover {YEAR}, whole world (COG)",
        "description": f"All {len(urls)} tiles of {YEAR} in one 8-bit RGBA image in Web Mercator (EPSG:3857) at about 2.4 km, "
                       "in the class colors. Made from the tiles' internal overviews with mode resampling, so it is for display only.",
        "proj:code": "EPSG:3857", "start_datetime": f"{YEAR}-01-01T00:00:00Z", "end_datetime": f"{YEAR}-12-31T23:59:59Z",
        **fields(ov)}
    d["thumbnail"] = {
        "href": "./thumbnail.png", "type": "image/png", "roles": ["thumbnail"], "title": f"Land cover {YEAR} preview",
        "description": f"The {YEAR} overview from 60°S to about 84°N, 900 by 600 pixels, with no basemap.", **fields(th)}
    open(f"{REPO}/data/derived-assets.json", "w").write(json.dumps(d, indent=2) + "\n")
    print(ov, os.path.getsize(ov), th, os.path.getsize(th))


if __name__ == "__main__":
    main()

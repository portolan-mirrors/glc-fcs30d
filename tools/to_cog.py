"""Split one GLC_FCS30D tile into single-band, display-ready COGs (one per year).

usage: to_cog.py SRC.tif OUT_DIR
Pixels are copied unchanged. Adds: nodata 0, the guide's color table, mode overviews, embedded stats.
Writes OUT_DIR/<year>/<year>-<tile>/<year>-<tile>.tif.
"""
import os, re, sys
import numpy as np
from osgeo import gdal

sys.path.insert(0, os.path.dirname(__file__))
from classes import CLASSES, FILL_COLOR, FILL_VALUES, NODATA

gdal.UseExceptions()

# The upstream file names say which years their bands hold (user guide, "Note").
ZSTD_LEVEL = 6  # measured on W165N65: 15% faster than 9 for 2.7% more bytes; 3 cost 15% more bytes
YEARS = {"5years": [1985, 1990, 1995], "Annual": list(range(2000, 2023))}


def color_table():
    ct = gdal.ColorTable()
    for v in range(256):
        if v in CLASSES:
            ct.SetColorEntry(v, (*CLASSES[v][1], 255))
        elif v in FILL_VALUES and v != NODATA:
            ct.SetColorEntry(v, (*FILL_COLOR, 255))
        else:  # nodata and unused values draw transparent
            ct.SetColorEntry(v, (0, 0, 0, 0))
    return ct


def split_bands(ds, paths):
    """Write each band to its own GTiff, decoding every source block once. Return per-band value counts.

    The upstream files are pixel-interleaved, so reading one band decodes all of them.
    The split files reuse the source block shape, so every split tile is written exactly once.
    """
    bx, by = ds.GetRasterBand(1).GetBlockSize()
    xs, ys = ds.RasterXSize, ds.RasterYSize
    drv = gdal.GetDriverByName("GTiff")
    outs = []
    for p in paths:
        o = drv.Create(p, xs, ys, 1, gdal.GDT_Byte, [
            "TILED=YES", f"BLOCKXSIZE={bx}", f"BLOCKYSIZE={by}", "COMPRESS=ZSTD", "ZSTD_LEVEL=1", "BIGTIFF=YES"])
        o.SetGeoTransform(ds.GetGeoTransform())
        o.SetProjection(ds.GetProjection())
        outs.append(o)
    counts = np.zeros((len(paths), 256), dtype=np.int64)
    for y0 in range(0, ys, by):
        for x0 in range(0, xs, bx):
            block = ds.ReadAsArray(x0, y0, min(bx, xs - x0), min(by, ys - y0))  # one source block, all bands
            for i, o in enumerate(outs):
                o.GetRasterBand(1).WriteArray(block[i], x0, y0)
                counts[i] += np.bincount(block[i].ravel(), minlength=256)
    for o in outs:
        o.FlushCache()
    del outs
    assert all(c.sum() == xs * ys for c in counts)
    return counts


def stats_from_counts(c):
    """Exact GDAL band statistics over the valid (non-nodata) pixels, from a 256-bin value count."""
    v = np.arange(256)
    valid = c.copy()
    valid[NODATA] = 0
    n = valid.sum()
    if n == 0:
        raise ValueError("band holds only nodata")
    mean = (v * valid).sum() / n
    return {
        "STATISTICS_MINIMUM": int(v[valid > 0].min()), "STATISTICS_MAXIMUM": int(v[valid > 0].max()),
        "STATISTICS_MEAN": float(mean), "STATISTICS_STDDEV": float(np.sqrt((valid * (v - mean) ** 2).sum() / n)),
        "STATISTICS_VALID_PERCENT": float(100 * n / c.sum()),
    }


def convert(src, out_dir, delete_src=False):
    """Yield (year, cog_path, value_counts) as each COG is written, so a caller can upload and delete it first.

    delete_src removes src once its bands are split, which frees its space before the COGs are written.
    """
    tile, kind = re.search(r"_([EW]\d+[NS]\d+)_(5years|Annual)_", os.path.basename(src)).groups()
    ds = gdal.Open(src)
    years = YEARS[kind]
    assert ds.RasterCount == len(years), (src, ds.RasterCount)
    split_dir = os.path.join(out_dir, "_split", tile)
    os.makedirs(split_dir, exist_ok=True)
    splits = [os.path.join(split_dir, f"{year}.tif") for year in years]
    counts = split_bands(ds, splits)
    ds = None
    if delete_src:
        os.remove(src)
    for split, year, c in zip(splits, years, counts):
        dst = os.path.join(out_dir, str(year), f"{year}-{tile}", f"{year}-{tile}.tif")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        vrt = gdal.Translate("", split, format="VRT", noData=NODATA)
        b = vrt.GetRasterBand(1)
        b.SetColorTable(color_table())
        b.SetColorInterpretation(gdal.GCI_PaletteIndex)  # upstream tags the year bands as RGB
        b.SetDescription(f"Land cover {year}")
        for k, val in stats_from_counts(c).items():  # exact, so no separate statistics pass
            b.SetMetadataItem(k, str(val))
        # ZSTD, no predictor: smallest of ZSTD/DEFLATE/LZW/LERC on the pilot tiles
        gdal.Translate(dst, vrt, format="COG", creationOptions=[
            "COMPRESS=ZSTD", f"LEVEL={ZSTD_LEVEL}", "PREDICTOR=NO", "BLOCKSIZE=512",
            "RESAMPLING=MODE", "OVERVIEW_RESAMPLING=MODE", "NUM_THREADS=1", "BIGTIFF=IF_SAFER"])
        vrt = None
        os.remove(split)
        yield year, dst, c
    os.rmdir(split_dir)


if __name__ == "__main__":
    for _, path, _ in convert(*sys.argv[1:3]):
        print(path)

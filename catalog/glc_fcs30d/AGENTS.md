# Agent guide: GLC_FCS30D global 30 m land cover, 1985–2022

Every claim here is quoted from the producer's user guide or measured from the published files.

## What this holds

- **Items.** There are 24,986 STAC items, one for each 5° tile (961) and year (26: 1985, 1990, 1995, 2000–2022). The item id is `<year>-<tile>`, for example `2022-E0N50`. The tile name is the upper-left corner: `E0N50` covers 0°E to 5°E, 45°N to 50°N.
- **Asset.** Each item has one asset, `data`: a single-band uint8 COG of class values in EPSG:4326, with nodata 0.
- **COG URL.** The URL is `https://data.source.coop/portolan-mirrors/glc-fcs30d/glc_fcs30d/<year>/<band>/<id>/<id>.tif`. `<band>` is the 10° longitude band of the source ZIP, for example `E0-E5` or `W165-W170`.
- **Classes.** The class list is `classification:classes` on the data asset and on `item_assets.data` in the collection. Each class has `value`, `name`, `title` and `color_hint`.

## How to find tiles

Query the item mirror. Do not walk 962 catalogs. Columns: `id`, `bbox` (struct of `xmin`, `ymin`, `xmax`, `ymax`), `start_datetime` and `end_datetime` (timestamp with time zone), and `assets.data.href`.

```sql
SELECT id, assets.data.href
FROM 'https://data.source.coop/portolan-mirrors/glc-fcs30d/glc_fcs30d/items.parquet'
WHERE start_datetime >= TIMESTAMP '2022-01-01' AND start_datetime < TIMESTAMP '2023-01-01'
  AND bbox.xmin <= 2.35 AND bbox.xmax >= 2.35 AND bbox.ymin <= 48.86 AND bbox.ymax >= 48.86;
```

This returns `2022-E0N50`. Read a window with `gdal_translate -projwin <ulx> <uly> <lrx> <lry> /vsicurl/<href> out.tif`.

## Quirks that give wrong answers

- **Open ocean is class 210, water body, not nodata 0.** To separate inland water from sea, use a land mask. This dataset cannot tell them apart.
- **Pixels are in degrees.** A pixel is 0.000269494585236° on each side. Its ground area falls with the cosine of latitude. Do not multiply pixel counts by 900 m².
- **Tiles overlap by 0.75 pixel at each east and south edge, and their grids are offset.** Summing per-tile counts double-counts the edge strip. Mosaic with `gdalbuildvrt` first, or clip each tile to its exact 5° cell.
- **Pre-2000 years are 5-year steps.** The years are 1985, 1990 and 1995. There is no map for 1986–1989, 1991–1994 or 1996–1999. Do not interpolate across the gap without saying so.
- **The source files disagree with the guide.** The 5-year source files are named `…_19852000_…_5years_…`, but the user guide calls them `19851995`. Their three bands are 1985, 1990 and 1995.
- **0 and 250.** The guide lists both as "Filled value". Value 0 is the declared nodata. Value 250 is not declared, but it appears in 294 COGs from 12 tiles, 2.6 million pixels in total, mostly in W100N80, W95N80, W90N80 and W85N80. Exclude 250 from class statistics.
- **Accuracy.** The guide reports an overall accuracy of 80.88% (±0.27%) for 10 major types, and 73.24% (±0.30%) for 17 LCCS level-1 types. The guide gives no accuracy for the 35 fine classes, so do not quote these figures for them.

## Provenance

This is a mirror of [doi:10.5281/zenodo.15063683](https://doi.org/10.5281/zenodo.15063683) (CC BY 4.0). The pixel values are unchanged from the source GeoTIFFs. Cite doi:10.5194/essd-16-1353-2024. The `updated` field of the collection is the time of the latest sync.

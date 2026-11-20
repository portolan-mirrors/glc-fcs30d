# AGENTS.md — GLC_FCS30D mirror

Guidance for AI agents and automated clients working with this catalog. Every claim here is quoted from the producer's user guide or measured from the published files.

## What this catalog holds

The root is `https://data.source.coop/portolan-mirrors/glc-fcs30d/catalog.json`. It holds one collection, `glc_fcs30d`: global land cover at 30 m in 35 classes. There are 24,986 single-band COGs, one for each 5° tile (961) and year (1985, 1990, 1995, 2000–2022). Each COG is one STAC item.

## How to read it

Find tiles with the item mirror, `https://data.source.coop/portolan-mirrors/glc-fcs30d/glc_fcs30d/items.parquet`. Filter on `bbox.xmin`, `bbox.ymin`, `bbox.xmax`, `bbox.ymax` and `start_datetime`, and read `assets.data.href`. Then read pixels with GDAL from `/vsicurl/<href>`. The [collection agent guide](./glc_fcs30d/AGENTS.md) has a tested query.

## Join keys

There is one collection, so nothing joins. Within it, the item `id` is `<year>-<tile>`. The same `<tile>` across years is the same 5° cell on the same pixel grid, so one tile can be compared pixel by pixel across years.

## Quirks that produce silently wrong answers

- **Open ocean is class 210, water body, not nodata.**
- **The grid is EPSG:4326**, with pixels of 0.000269494585236°. Pixel area falls with the cosine of latitude.
- **Adjacent tiles overlap by 0.75 pixel.** Summed per-tile counts double-count the edges.
- **Before 2000, maps are every 5 years only.**

The [collection agent guide](./glc_fcs30d/AGENTS.md) explains each of these.

## Structure

The root catalog carries an absolute `self` link. Structural links are relative. Each item's data asset `href` is an absolute https URL, so rows in `items.parquet` resolve on their own.

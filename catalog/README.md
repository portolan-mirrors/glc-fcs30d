# GLC_FCS30D: Global 30 m Land Cover Dynamics, 1985–2022

A cloud-native mirror of [GLC_FCS30D v2](https://doi.org/10.5281/zenodo.15063683): land cover of the whole world at 30 m, in 35 classes. There are maps for 1985, 1990, 1995 and every year from 2000 to 2022.

## What is here

One collection, [`glc_fcs30d`](./glc_fcs30d/README.md):
- **24,986 maps.** Each is a Cloud Optimized GeoTIFF: one for each of 961 tiles of 5° by 5°, for each of 26 years. Each COG has the class colors in its color table.
- **One STAC item per COG.** The items are grouped by year, then by 10° longitude band.
- **[`items.parquet`](./glc_fcs30d/items.parquet).** Every item in one stac-geoparquet file, for search.

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), as given on the Zenodo record. The rights holders are the producers: Liangyun Liu, Xiao Zhang and Zhehua Li, Aerospace Information Research Institute, Chinese Academy of Sciences. Cite [doi:10.5194/essd-16-1353-2024](https://doi.org/10.5194/essd-16-1353-2024).

## Provenance

This is a mirror, not the official publication. The upstream is the Zenodo record [doi:10.5281/zenodo.15063683](https://doi.org/10.5281/zenodo.15063683), version v2 of 2025-03-21. The mirror was synced once. The `updated` field on this catalog records the time of that sync. The pixel values are unchanged. Only the file layout changed: one COG per tile and year, instead of one multi-year GeoTIFF per tile inside 36 ZIP files. The tools and the metadata are in <https://github.com/nlebovits/glc-fcs30d>.

## Access

Find the 2022 tile that holds a point, with no download:

```sql
SELECT id, assets.data.href
FROM 'https://data.source.coop/portolan-mirrors/glc-fcs30d/glc_fcs30d/items.parquet'
WHERE start_datetime >= TIMESTAMP '2022-01-01' AND start_datetime < TIMESTAMP '2023-01-01'
  AND bbox.xmin <= 2.35 AND bbox.xmax >= 2.35 AND bbox.ymin <= 48.86 AND bbox.ymax >= 48.86;
```

Then open the `href` with GDAL as `/vsicurl/<href>`. See the [collection README](./glc_fcs30d/README.md) for the classes and the known issues.

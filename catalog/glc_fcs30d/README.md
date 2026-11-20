# GLC_FCS30D global 30 m land cover, 1985–2022

Land cover of the whole world at 30 m, in 35 classes, from 1985 to 2022. GLC_FCS30D v2 was made by Liangyun Liu, Xiao Zhang and Zhehua Li at the Aerospace Information Research Institute, Chinese Academy of Sciences (AIRCAS). This collection is a mirror. The original is [doi:10.5281/zenodo.15063683](https://doi.org/10.5281/zenodo.15063683).

From the producer's user guide:

> GLC_FCS30D is the first global fine land cover dynamic product at a 30-meter resolution that adopts continuous change detection. It utilizes a refined classification system containing 35 land-cover categories and covers the time span from 1985 to 2022. Before the year 2000, the update cycle was every 5 years, while after 2000, it is updated annually. […] [It] was validated to achieve an overall accuracy of 80.88% (±0.27%) for the basic classification system 10 major land-cover types) and 73.24% (±0.30%) for the LCCS level-1 validation system (17 LCCS land-cover types).

## What is here

- **24,986 maps.** There is one map for each of 961 tiles of 5° by 5°, for each of 26 years: 1985, 1990, 1995, and every year from 2000 to 2022.
- **One COG per map.** Each map is a single-band Cloud Optimized GeoTIFF of class values (uint8) in EPSG:4326, with an embedded color table, nodata 0, internal overviews and embedded statistics. Each COG is one STAC item.
- **Grouping.** The items are grouped by year, then by 10° longitude band. The bands match the 36 source ZIP files.
- **[`items.parquet`](./items.parquet)** has every item as one row (stac-geoparquet). Query it to find tiles by place and year without walking the catalogs.

## How to use it

Open a tile with no download:

```sh
gdalinfo /vsicurl/https://data.source.coop/portolan-mirrors/glc-fcs30d/glc_fcs30d/2022/E0-E5/2022-E0N50/2022-E0N50.tif
```

Cut a window: central Paris in 2022, which is mostly class 190, impervious surfaces:

```sh
gdal_translate -projwin 2.25 48.95 2.45 48.80 \
  /vsicurl/https://data.source.coop/portolan-mirrors/glc-fcs30d/glc_fcs30d/2022/E0-E5/2022-E0N50/2022-E0N50.tif paris-2022.tif
```

Find the tile for a point and a year with DuckDB:

```sql
SELECT id, assets.data.href
FROM 'https://data.source.coop/portolan-mirrors/glc-fcs30d/glc_fcs30d/items.parquet'
WHERE start_datetime >= TIMESTAMP '2022-01-01' AND start_datetime < TIMESTAMP '2023-01-01'
  AND bbox.xmin <= 2.35 AND bbox.xmax >= 2.35 AND bbox.ymin <= 48.86 AND bbox.ymax >= 48.86;
```

To mosaic several tiles, pass their `/vsicurl/` URLs to `gdalbuildvrt`.

## Classes

The class values, titles and RGB colors are copied from the user guide's table "The fine classification system containing 35 land-cover sub-categories". They are in `classification:classes` on each item's data asset and in the color table of each COG. The guide lists `0, 250` as "Filled value". These COGs declare 0 as nodata. 250 keeps its value.

| Value | Class | Value | Class |
|---|---|---|---|
| 10 | Rainfed cropland | 122 | Deciduous shrubland |
| 11 | Herbaceous cover cropland | 130 | Grassland |
| 12 | Tree or shrub cover (Orchard) cropland | 140 | Lichens and mosses |
| 20 | Irrigated cropland | 150 | Sparse vegetation (fc<0.15) |
| 51 | Open evergreen broadleaved forest | 152 | Sparse shrubland (fc<0.15) |
| 52 | Closed evergreen broadleaved forest | 153 | Sparse herbaceous (fc<0.15) |
| 61 | Open deciduous broadleaved forest (0.15<fc<0.4) | 181 | Swamp |
| 62 | Closed deciduous broadleaved forest (fc>0.4) | 182 | Marsh |
| 71 | Open evergreen needle-leaved forest (0.15<fc<0.4) | 183 | Flooded flat |
| 72 | Closed evergreen needle-leaved forest (fc>0.4) | 184 | Saline |
| 81 | Open deciduous needle-leaved forest (0.15<fc<0.4) | 185 | Mangrove |
| 82 | Closed deciduous needle-leaved forest (fc>0.4) | 186 | Salt marsh |
| 91 | Open mixed leaf forest (broadleaved and needle-leaved) | 187 | Tidal flat |
| 92 | Closed mixed leaf forest (broadleaved and needle-leaved) | 190 | Impervious surfaces |
| 120 | Shrubland | 200 | Bare areas |
| 121 | Evergreen shrubland | 201 | Consolidated bare areas |
| | | 202 | Unconsolidated bare areas |
| | | 210 | Water body |
| | | 220 | Permanent ice and snow |

fc is fractional cover.

## Known issues

- **Open ocean is class 210, water body, not nodata.** For example, tile E105S10 is all 210 in 2022.
- **Tiles overlap and their pixel grids do not line up.** A tile is 18,554 pixels of 0.000269494585236° wide, which is 5.0002°, not 5°. Each tile overlaps its east and south neighbors by 0.75 pixel. Pixel counts summed over tiles count that edge strip twice.
- **Pixels are not equal in area.** The grid is in degrees, so a pixel near the poles covers less ground than one at the equator. Weight pixel counts by the cosine of latitude to estimate area.
- **Value 250, "Filled value", is in the data.** It appears in 294 of the 24,986 COGs, from 12 tiles, 2.6 million pixels in total. Most of them are in the Arctic tiles W100N80, W95N80, W90N80 and W85N80. It is not declared as nodata, so treat it as missing data yourself.
- **There are no maps for 1986–1989, 1991–1994 or 1996–1999.**
- **The 5-year source files are named `19852000`.** The user guide names them `19851995`. Their three bands are 1985, 1990 and 1995.

## How this mirror was made

`tools/pipeline.py` in the [source repository](https://github.com/nlebovits/glc-fcs30d) reads each tile's two GeoTIFFs out of the Zenodo ZIPs with HTTP range requests. It then writes each band as its own COG: ZSTD compression, 512-pixel blocks, mode-resampled overviews, and the guide's colors as the color table. The pixel values are not changed. Each COG's size and SHA-256 checksum are recorded in its item. The `source-*` assets of the collection link the original ZIPs, with their MD5 checksums from Zenodo.

## License and citation

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), from the Zenodo record. Cite the paper:

> Zhang, X., Zhao, T., Xu, H., Liu, W., Wang, J., Chen, X., & Liu, L., 2024. GLC_FCS30D: The first global 30-m land-cover dynamic monitoring product with a fine classification system from 1985 to 2022 using dense time-series Landsat imagery and continuous change-detection method. Earth Syst. Sci. Data, 16, 1353–1381, https://doi.org/10.5194/essd-16-1353-2024.

The user guide adds: "If you plan to use our data in a scientific analysis paper, we strongly recommend contacting us in advance to seek opinions and consider our contributions in the acknowledgments or as co-authors." The guide gives the contact as liuly@radi.ac.cn.

Report a problem with this mirror at <https://github.com/nlebovits/glc-fcs30d/issues>.

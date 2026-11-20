# glc-fcs30d

The tools and metadata behind the Portolan mirror of
[GLC_FCS30D v2](https://doi.org/10.5281/zenodo.15063683), a global 30 m land cover
time series (1985–2022, 35 classes) by the Aerospace Information Research Institute,
Chinese Academy of Sciences.

- **Catalog:** <https://data.source.coop/portolan-mirrors/glc-fcs30d/catalog.json>
- **Browse:** <https://browser.portolan-sdi.org/#/external/data.source.coop/portolan-mirrors/glc-fcs30d/catalog.json>
- **Hosting:** <https://source.coop/portolan-mirrors/glc-fcs30d>

The published documentation is [catalog/README.md](catalog/README.md) and
[catalog/glc_fcs30d/README.md](catalog/glc_fcs30d/README.md). This file is about the repository.

## How the mirror is built

1. `tools/zenodo_zip.py` lists the members of the 36 ZIPs on Zenodo with HTTP range
   requests (`data/zip-members.json`).
2. `tools/pipeline.py WORKERS` takes each of the 961 tiles: it range-reads the tile's two
   GeoTIFFs out of their ZIP, writes one COG per year with `tools/to_cog.py`, uploads it,
   checks the uploaded size, and records its metadata. It resumes from `../state/`.
   Run it under a memory cap, for example
   `systemd-run --user --scope -p MemoryMax=100G env GDAL_CACHEMAX=256 python3 -I tools/pipeline.py 80`.
3. Merge `../state/meta/*.jsonl` into `data/cogs.jsonl`.
4. `python3 tools/build_stac.py` writes the item tree and `collection.json`.
5. `tools/items_parquet.py` (with stac-geoparquet and geoparquet-io) and
   `python3 tools/overview.py` write the item mirror, the overview and the thumbnail.
   Then run `tools/build_stac.py` again.
6. `python3 tests/run_all.py` runs the gates. `catalog.publish.yaml` shows the publish
   commands.

## Report a problem

Open an issue at <https://github.com/portolan-mirrors/glc-fcs30d/issues>.

## License

The code is Apache-2.0 (see [LICENSE](LICENSE)). The data is CC BY 4.0, from its producers.

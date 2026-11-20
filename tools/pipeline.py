"""Fetch -> convert -> record -> upload -> verify -> delete, one GLC_FCS30D tile at a time.

usage: pipeline.py WORKERS [TILE ...]     (no tiles = all 961)
Run it under a memory cap (systemd-run --user --slice=...) with GDAL_CACHEMAX=256.
Uploads go through the Source Cooperative data proxy with `source-coop creds` credentials.
Resumable: a tile with STATE/done/<tile> is skipped. STATE defaults to ../state beside the repo.
Writes one JSON line per COG to STATE/meta/<tile>.jsonl, the input for tools/build_stac.py.
"""
import datetime, hashlib, json, os, re, shutil, subprocess, sys, time, traceback
from multiprocessing import Pool

from osgeo import gdal

sys.path.insert(0, os.path.dirname(__file__))
import to_cog, zenodo_zip

gdal.UseExceptions()
os.environ.pop("AWS_PROFILE", None)  # a named profile would override the source-coop credentials
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.environ.get("STATE", os.path.join(os.path.dirname(REPO), "state"))
WORK = os.environ.get("WORK", f"{W}/work")  # point at a tmpfs: the intermediates are ~2 GB of writes per tile
zenodo_zip.TAIL_CACHE = f"{W}/zip-tails"  # each zip directory is fetched once per run
REC = json.load(open(f"{REPO}/data/zenodo-record.json"))
MEMBERS = json.load(open(f"{REPO}/data/zip-members.json"))
BUCKET, PRODUCT, PREFIX = "portolan-mirrors", "glc-fcs30d", "glc_fcs30d"
ENDPOINT = "https://data.source.coop"
COG_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"
SC = os.path.expanduser("~/.cargo/bin/source-coop")

# tile -> {kind: (member, zip band like "E10-E15")}
TILES = {}
for z, ms in MEMBERS.items():
    for name, _ in ms:
        m = re.search(r"_([EW]\d+[NS]\d+)_(5years|Annual)_V1\.1\.tif$", name)
        if m:
            TILES.setdefault(m[1], {})[m[2]] = (name, re.search(r"maps_(.+)\.zip$", z)[1])
assert len(TILES) == 961 and all(len(v) == 2 for v in TILES.values())


class Uploader:
    """aws CLI v2 uploads with source-coop credentials, refreshed every 15 minutes (they last an hour).

    The CLI, not boto3: the proxy rejects this box's botocore 1.34 PutObject as carrying unsigned headers.
    """

    def __init__(self):
        self.env, self.at = None, 0

    def creds(self, force=False):
        if force or self.env is None or time.time() - self.at > 900:
            out = subprocess.run([SC, "creds", "--format", "env"], check=True, capture_output=True, text=True).stdout
            env = dict(l.removeprefix("export ").split("=", 1) for l in out.splitlines() if "=" in l)
            self.env = {**os.environ, **{k: v.strip("'\"") for k, v in env.items()}, "AWS_ENDPOINT_URL_S3": ENDPOINT}
            self.env.pop("AWS_PROFILE", None)
            self.at = time.time()
        return self.env

    def put(self, path, key):
        uri = f"s3://{BUCKET}/{PRODUCT}/{key}"
        for attempt in range(4):
            env = self.creds(force=attempt > 0)
            try:
                subprocess.run(["aws", "s3", "cp", "--only-show-errors", "--content-type", COG_TYPE, path, uri],
                               env=env, check=True, capture_output=True, text=True)
                head = subprocess.run(["aws", "s3api", "head-object", "--bucket", BUCKET, "--key", f"{PRODUCT}/{key}",
                                       "--query", "ContentLength"], env=env, check=True, capture_output=True, text=True)
                if int(head.stdout) != os.path.getsize(path):
                    raise IOError(f"size mismatch after upload {uri}: {head.stdout.strip()} != {os.path.getsize(path)}")
                return
            except (subprocess.CalledProcessError, IOError, ValueError) as e:
                if attempt == 3:
                    raise RuntimeError(f"upload failed {uri}: {getattr(e, 'stderr', e)}") from e
                time.sleep(5 * (attempt + 1))


UP = Uploader()


def describe(path, counts):
    ds = gdal.Open(path)
    gt = ds.GetGeoTransform()
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            sha.update(chunk)
    stats = to_cog.stats_from_counts(counts)
    return {
        "size": os.path.getsize(path), "checksum": "1220" + sha.hexdigest(),
        "shape": [ds.RasterYSize, ds.RasterXSize], "transform": list(gt),
        "bbox": [gt[0], gt[3] + gt[5] * ds.RasterYSize, gt[0] + gt[1] * ds.RasterXSize, gt[3]],
        "stats": {k.removeprefix("STATISTICS_"): v for k, v in stats.items()},
        "histogram": {int(v): int(c) for v, c in enumerate(counts) if c},
    }


def run_tile(tile):
    done = f"{W}/done/{tile}"
    if os.path.exists(done):
        return tile, "skip"
    work = f"{WORK}/{tile}"
    shutil.rmtree(work, ignore_errors=True)
    try:
        metas = []
        for kind, (member, band) in sorted(TILES[tile].items()):
            src = f"{work}/{os.path.basename(member)}"
            os.makedirs(work, exist_ok=True)
            zenodo_zip.get(REC, member, src)
            fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for year, p, counts in to_cog.convert(src, f"{work}/out", delete_src=True):
                key = f"{PREFIX}/{year}/{band}/{year}-{tile}/{year}-{tile}.tif"
                meta = {"tile": tile, "year": year, "band": band, "key": key, "source_member": member,
                        "fetched_at": fetched_at, **describe(p, counts)}
                UP.put(p, key)
                metas.append(meta)
                os.remove(p)
        assert len(metas) == 26, (tile, len(metas))
        os.makedirs(f"{W}/meta", exist_ok=True)
        with open(f"{W}/meta/{tile}.jsonl", "w") as f:
            f.writelines(json.dumps(m) + "\n" for m in metas)
        open(done, "w").close()
        shutil.rmtree(work)
        return tile, "ok"
    except Exception:
        with open(f"{W}/errors.log", "a") as f:
            f.write(f"== {tile}\n{traceback.format_exc()}\n")
        return tile, "FAILED"


if __name__ == "__main__":
    os.makedirs(f"{W}/done", exist_ok=True)
    tiles = sys.argv[2:] or sorted(TILES)
    from multiprocessing import Lock, Value
    with Pool(int(sys.argv[1]), maxtasksperchild=1, initializer=zenodo_zip.set_limiter,
              initargs=(Lock(), Value("d", 0.0))) as pool:
        for tile, status in pool.imap_unordered(run_tile, tiles):
            print(tile, status, flush=True)

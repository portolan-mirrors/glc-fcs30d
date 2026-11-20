"""Read members of the GLC_FCS30D Zenodo zips over HTTP range requests.

usage:
  zenodo_zip.py list ZENODO_JSON OUT_JSON          # member listing of every zip
  zenodo_zip.py get  ZENODO_JSON MEMBER_NAME OUT   # extract one member, CRC-checked by zipfile
"""
import http.client, io, json, os, random, shutil, sys, time, urllib.request, zipfile

# Zenodo allows 133 requests/min per IP. A (Lock, Value) shared by every worker process spaces requests
# at least INTERVAL seconds apart; pipeline.py installs it with set_limiter() in each pool worker.
LIMITER, INTERVAL = None, 0.6
PREFETCH_CHUNK = 64 << 20  # requests, not bytes, are the scarce resource: 47 MB median member -> 1 request
TAIL = 2 << 20  # the end record and central directory of every zip here fit in the last 2 MB
TAIL_CACHE = os.environ.get("ZIP_TAIL_CACHE")  # a directory: each zip's tail is fetched once per run, not per member


def set_limiter(lock, next_slot):
    global LIMITER
    LIMITER = (lock, next_slot)


def wait_for_slot():
    if LIMITER is None:
        return
    lock, next_slot = LIMITER
    with lock:
        now = time.time()
        start = max(now, next_slot.value)
        next_slot.value = start + INTERVAL
    time.sleep(start - now)
from concurrent.futures import ThreadPoolExecutor


class HTTPFile(io.RawIOBase):
    """A seekable view of a remote file. Reads inside a prefetched span come from memory."""

    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.cache_start, self.cache = 0, b""
        self.tail_start, self.tail = 0, b""

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def fetch(self, start, end):
        """Bytes [start, end) in one range request, retried."""
        n = end - start
        for attempt in range(30):
            wait_for_slot()
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end - 1}"})
                with urllib.request.urlopen(req, timeout=600) as r:
                    if r.status != 206:
                        raise IOError(f"expected 206, got {r.status}")
                    data = r.read()
                if len(data) != n:
                    raise IOError(f"short read {len(data)} of {n}")
                return data
            except urllib.error.HTTPError as e:
                if attempt == 29 or e.code not in (429, 500, 502, 503, 504):
                    raise
                # Zenodo's 429 can carry a near-zero Retry-After; a lockstep retry then fails again
                time.sleep(max(60, int(e.headers.get("Retry-After") or 0)) * random.uniform(1, 1.5))
            except (IOError, OSError, http.client.HTTPException):  # IncompleteRead is not an OSError
                if attempt == 29:
                    raise
                time.sleep(2 ** min(attempt, 6))

    def prefetch(self, start, end, chunk=PREFETCH_CHUNK):
        """Hold [start, end) in memory, fetched as parallel range requests (Zenodo serves ~1 MB/s per connection)."""
        end = min(end, self.size)
        spans = [(o, min(o + chunk, end)) for o in range(start, end, chunk)]
        with ThreadPoolExecutor(len(spans)) as ex:
            self.cache_start, self.cache = start, b"".join(ex.map(lambda sp: self.fetch(*sp), spans))

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        off, toff = self.pos - self.cache_start, self.pos - self.tail_start
        if 0 <= off < len(self.cache):
            data = self.cache[off:off + n]
        elif self.tail and 0 <= toff < len(self.tail):
            data = self.tail[toff:toff + n]
        else:
            data = self.fetch(self.pos, self.pos + n)
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def open_zip(f):
    # 1 MB reads: enough for the end record and central directory in one or two requests
    raw = HTTPFile(f["links"]["self"], f["size"])
    raw.tail_start = max(0, f["size"] - TAIL)
    if TAIL_CACHE:
        path = os.path.join(TAIL_CACHE, f["key"] + ".tail")
        if not os.path.exists(path):
            os.makedirs(TAIL_CACHE, exist_ok=True)
            tmp = f"{path}.{os.getpid()}"
            open(tmp, "wb").write(raw.fetch(raw.tail_start, f["size"]))
            os.replace(tmp, path)
        raw.tail = open(path, "rb").read()
        assert len(raw.tail) == f["size"] - raw.tail_start
    return raw, zipfile.ZipFile(io.BufferedReader(raw, 1 << 20))


def zips(rec):
    return [f for f in rec["files"] if f["key"].endswith(".zip")]


def list_all(rec):
    def members(f):
        raw, z = open_zip(f)
        with z:
            return f["key"], [(i.filename, i.file_size) for i in z.infolist()]
    with ThreadPoolExecutor(8) as ex:
        return dict(ex.map(members, zips(rec)))


def get(rec, member, out):
    zipname = member.split("/")[0] + ".zip"
    f = next(f for f in zips(rec) if f["key"] == zipname)
    tmp = out + ".part"
    raw, z = open_zip(f)
    with z:
        info = z.getinfo(member)
        # local header (30 bytes + name + an extra field of at most 64 KiB) + data + data descriptor
        raw.prefetch(info.header_offset, info.header_offset + 30 + len(info.orig_filename.encode()) + 65536 + info.compress_size + 24)
        with z.open(info) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst, 8 << 20)  # zipfile raises BadZipFile on CRC mismatch
    os.replace(tmp, out)


if __name__ == "__main__":
    cmd, rec = sys.argv[1], json.load(open(sys.argv[2]))
    if cmd == "list":
        json.dump(list_all(rec), open(sys.argv[3], "w"))
    else:
        get(rec, sys.argv[3], sys.argv[4])

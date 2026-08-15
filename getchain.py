#!/usr/bin/env python3
"""
ChainStrap - bootstrap a blockchain node from a snapshot published on IPFS.

  python3 getchain.py RVN              # mainnet
  python3 getchain.py RVN --testnet    # testnet
  python3 getchain.py --list           # what's available

Only the Python standard library is required, so this file runs as-is on
Windows, macOS and Linux.  If an IPFS daemon is listening on 127.0.0.1:5001 it
is used; otherwise the parts are fetched from public IPFS gateways over HTTPS,
resuming where they left off if the connection drops.

This script writes only inside the block/chainstate folders of your data
directory.  It never reads, moves or deletes wallet.dat or any .conf file.
"""

DOMAIN = "https://chainstrap.com/"

# Tried in order, after any baseurl named in the snapshot metadata.
GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://dweb.link/ipfs/",
    "https://w3s.link/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://4everland.io/ipfs/",
]

IPFS_API = "http://127.0.0.1:5001/api/v0"

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import time
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHUNK = 1 << 20  # 1 MiB


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def human(n):
    """Bytes as a short human-readable string."""
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0 or unit == "TB":
            return "%.1f %s" % (n, unit) if unit not in ("B", "KB") else "%d %s" % (n, unit)
        n /= 1024.0


def duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm%02ds" % (seconds // 60, seconds % 60)
    return "%dh%02dm" % (seconds // 3600, (seconds % 3600) // 60)


def log(msg=""):
    print(msg, flush=True)


def fetch_json(url):
    req = Request(url, headers={"User-Agent": "chainstrap-getchain/2"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def confirm(question, assume_yes):
    if assume_yes:
        return True
    if not sys.stdin or not sys.stdin.isatty():
        log("Not running interactively and --yes was not given; stopping.")
        return False
    try:
        answer = input(question + " [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        log("")
        return False
    return answer in ("y", "yes")


# --------------------------------------------------------------------------
# metadata
# --------------------------------------------------------------------------

def load_index(domain):
    """The list of chain codes this ChainStrap site publishes."""
    try:
        data = fetch_json(domain + "chains.json")
    except (URLError, HTTPError, ValueError) as exc:
        raise SystemExit("Could not read the chain index: %s" % exc)
    codes = []
    for entry in data.get("chains", []):
        code = entry if isinstance(entry, str) else entry.get("code")
        if code:
            codes.append(code)
    return codes


def load_config(domain, chain):
    url = "%s%s/%s-config.json" % (domain, chain, chain)
    try:
        return fetch_json(url)
    except HTTPError as exc:
        if exc.code == 404:
            raise SystemExit(
                "No config for '%s'. Run --list to see the published chains." % chain)
        raise SystemExit("Could not read %s: %s" % (url, exc))
    except (URLError, ValueError) as exc:
        raise SystemExit("Could not read %s: %s" % (url, exc))


def load_metadata(domain, chain, mode):
    url = "%s%s/%s-%s.json" % (domain, chain, chain, mode)
    try:
        return fetch_json(url)
    except HTTPError as exc:
        if exc.code == 404:
            raise SystemExit("No %s snapshot published for %s." % (mode, chain))
        raise SystemExit("Could not read %s: %s" % (url, exc))
    except (URLError, ValueError) as exc:
        raise SystemExit("Could not read %s: %s" % (url, exc))


def snapshot_parts(meta):
    """Normalize the metadata shapes this project has used over the years.

    Newest:  "parts": [{"cid": ..., "bytes": ..., "sha256": ...}, ...]
    Older:   "ipfs_hashes": [cid, ...]
    Oldest:  "ipfs_hash": cid
    """
    if isinstance(meta.get("parts"), list) and meta["parts"]:
        parts = []
        for item in meta["parts"]:
            if isinstance(item, str):
                parts.append({"cid": item})
            elif item.get("cid"):
                parts.append(dict(item))
        if parts:
            return parts
    if isinstance(meta.get("ipfs_hashes"), list) and meta["ipfs_hashes"]:
        return [{"cid": cid} for cid in meta["ipfs_hashes"]]
    if meta.get("ipfs_hash"):
        return [{"cid": meta["ipfs_hash"]}]
    raise SystemExit("Snapshot metadata lists no IPFS content IDs.")


# --------------------------------------------------------------------------
# where the chain data lives
# --------------------------------------------------------------------------

def os_key():
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "darwin"
    return "linux"


def expand(path):
    return os.path.expanduser(os.path.expandvars(path))


def resolve_datadir(config, mode, override):
    """Data directory for this OS and network, from the chain's config file."""
    if override:
        base = os.path.abspath(expand(override))
    else:
        key = os_key()
        dirs = config.get("datadir") or {}
        if key in dirs:
            base = expand(dirs[key])
        else:
            # Pre-2026 config layout: <os>_dir + subdir, with %USERDIR% to expand.
            legacy = {"windows": "win_dir", "darwin": "mac_dir", "linux": "lin_dir"}[key]
            root = config.get(legacy)
            sub = config.get("subdir")
            if not root or not sub:
                raise SystemExit(
                    "This chain's config has no data directory for %s." % platform.system())
            userdir = os.environ.get("APPDATA") if key == "windows" else os.path.expanduser("~")
            root = root.replace("%USERDIR%", userdir or os.path.expanduser("~"))
            if key == "linux" and not sub.startswith("."):
                sub = "." + sub
            base = expand(os.path.join(root.replace("/", os.sep), sub))
        base = os.path.abspath(base)

    if mode == "testnet":
        sub = config.get("testnet_dir")
        if not sub:
            raise SystemExit("This chain's config does not name a testnet directory.")
        base = os.path.join(base, sub)
    return base


def allowed_roots(config):
    """Top-level folders a snapshot is allowed to write into."""
    folders = config.get("folders")
    if isinstance(folders, dict):
        folders = list(folders.keys())
    if not isinstance(folders, list) or not folders:
        folders = ["blocks", "chainstate"]
    roots = set()
    for folder in folders:
        first = folder.replace("\\", "/").strip("/").split("/")[0]
        if first:
            roots.add(first)
    return roots


# --------------------------------------------------------------------------
# downloading
# --------------------------------------------------------------------------

class Progress(object):
    """One-line download progress that degrades gracefully when piped."""

    def __init__(self, label, total, already=0):
        self.label = label
        self.total = total
        self.done = already
        self.started_at = already  # so a resumed transfer reports the live rate
        self.start = time.time()
        self.last = 0.0
        self.tty = sys.stdout.isatty()

    def advance(self, n):
        self.done += n
        now = time.time()
        if now - self.last < 0.5 and self.done != self.total:
            return
        self.last = now
        elapsed = max(now - self.start, 0.001)
        rate = (self.done - self.started_at) / elapsed
        if self.total:
            pct = 100.0 * self.done / self.total
            eta = (self.total - self.done) / rate if rate > 0 else 0
            line = "  %s  %5.1f%%  %s / %s  %s/s  eta %s" % (
                self.label, pct, human(self.done), human(self.total),
                human(rate), duration(eta))
        else:
            line = "  %s  %s  %s/s" % (self.label, human(self.done), human(rate))
        if self.tty:
            sys.stdout.write("\r" + line.ljust(78))
            sys.stdout.flush()
        else:
            print(line, flush=True)

    def finish(self):
        if self.tty:
            sys.stdout.write("\r".ljust(80) + "\r")
            sys.stdout.flush()


def daemon_available():
    try:
        req = Request(IPFS_API + "/version", data=b"", method="POST")
        with urlopen(req, timeout=3) as resp:
            json.loads(resp.read().decode("utf-8"))
        return True
    except Exception:
        return False


def download_via_daemon(cid, dest, expected):
    """Stream a CID out of the local IPFS daemon. The daemon verifies hashes."""
    tmp = dest + ".part"
    req = Request("%s/cat?arg=%s" % (IPFS_API, cid), data=b"", method="POST")
    with urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
        bar = Progress("local IPFS", expected)
        while True:
            block = resp.read(CHUNK)
            if not block:
                break
            out.write(block)
            bar.advance(len(block))
        bar.finish()
    os.replace(tmp, dest)


def download_via_gateway(url, dest, expected):
    """HTTPS download with resume, so a dropped connection is cheap."""
    tmp = dest + ".part"
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    if expected and have >= expected:
        os.replace(tmp, dest)
        return

    headers = {"User-Agent": "chainstrap-getchain/2"}
    if have:
        headers["Range"] = "bytes=%d-" % have

    req = Request(url, headers=headers)
    with urlopen(req, timeout=120) as resp:
        if have and resp.status != 206:  # server ignored the range; start over
            have = 0
        total = expected
        if not total:
            length = resp.headers.get("Content-Length")
            if length and length.isdigit():
                total = int(length) + have
        mode = "ab" if have else "wb"
        with open(tmp, mode) as out:
            bar = Progress(url.split("/")[2], total, already=have)
            while True:
                block = resp.read(CHUNK)
                if not block:
                    break
                out.write(block)
                bar.advance(len(block))
            bar.finish()
    os.replace(tmp, dest)


def sha256_of(path, label):
    digest = hashlib.sha256()
    total = os.path.getsize(path)
    bar = Progress(label, total)
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            digest.update(block)
            bar.advance(len(block))
    bar.finish()
    return digest.hexdigest()


def gateway_urls(part, meta, override):
    cid = part["cid"]
    bases = []
    if override:
        bases.append(override)
    else:
        baseurl = meta.get("baseurl")
        # cloudflare-ipfs.com was retired in 2024 but lives on in old metadata.
        if baseurl and "cloudflare-ipfs.com" not in baseurl:
            bases.append(baseurl)
        bases.extend(GATEWAYS)
    seen, urls = set(), []
    for base in bases:
        base = base if base.endswith("/") else base + "/"
        if base not in seen:
            seen.add(base)
            urls.append(base + cid)
    return urls


def fetch_part(part, index, count, meta, workdir, args, use_daemon):
    cid = part["cid"]
    dest = os.path.join(workdir, cid)
    expected = part.get("bytes")

    log("[%d/%d] %s%s" % (index, count, cid, "  (%s)" % human(expected) if expected else ""))

    if os.path.exists(dest) and (not expected or os.path.getsize(dest) == expected):
        log("  already downloaded")
    else:
        errors = []
        if use_daemon:
            try:
                download_via_daemon(cid, dest, expected)
            except Exception as exc:
                errors.append("local daemon: %s" % exc)
        if not os.path.exists(dest):
            for url in gateway_urls(part, meta, args.gateway):
                try:
                    download_via_gateway(url, dest, expected)
                    break
                except (URLError, HTTPError, OSError) as exc:
                    errors.append("%s: %s" % (url.split("/")[2], exc))
                    log("  %s failed (%s), trying the next gateway" % (url.split("/")[2], exc))
        if not os.path.exists(dest):
            raise SystemExit("Could not download %s.\n  %s" % (cid, "\n  ".join(errors)))

    if part.get("sha256"):
        actual = sha256_of(dest, "verifying")
        if actual != part["sha256"]:
            os.remove(dest)
            raise SystemExit(
                "Checksum mismatch on %s - the file was deleted, please re-run." % cid)
        log("  checksum ok")
    return dest


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def safe_members(archive, roots, datadir):
    """Yield members that are safe to write, refusing anything outside `roots`.

    Guards against absolute paths, .. traversal and symlink members, and keeps
    the archive from reaching wallet.dat or config files even if it tried.
    """
    skipped = []
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if name.endswith("/"):
            continue
        if os.path.isabs(name) or name.startswith("/") or ".." in name.split("/"):
            skipped.append(name)
            continue
        if (info.external_attr >> 16) & 0xA000 == 0xA000:  # symlink
            skipped.append(name)
            continue
        if name.split("/")[0] not in roots:
            skipped.append(name)
            continue
        target = os.path.realpath(os.path.join(datadir, *name.split("/")))
        try:
            inside = os.path.commonpath([target, os.path.realpath(datadir)]) == \
                os.path.realpath(datadir)
        except ValueError:  # different drives on Windows
            inside = False
        if not inside:
            skipped.append(name)
            continue
        yield info
    if skipped:
        log("  skipped %d entr%s outside %s: %s"
            % (len(skipped), "y" if len(skipped) == 1 else "ies",
               "/".join(sorted(roots)), ", ".join(skipped[:5])))


def extract(zip_path, datadir, roots):
    with zipfile.ZipFile(zip_path) as archive:
        members = list(safe_members(archive, roots, datadir))
        total = sum(m.file_size for m in members)
        bar = Progress("extracting", total)
        for info in members:
            archive.extract(info, datadir)
            bar.advance(info.file_size)
        bar.finish()
    log("  extracted %d files" % len(members))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="getchain.py",
        description="Download a blockchain snapshot from IPFS and unpack it "
                    "into the right data directory for this computer.")
    parser.add_argument("chain", nargs="?", help="chain code, e.g. RVN")
    parser.add_argument("network", nargs="?", choices=["mainnet", "testnet"],
                        help="network (may also be given as --testnet)")
    parser.add_argument("--testnet", action="store_true", help="use the testnet snapshot")
    parser.add_argument("--list", action="store_true", dest="list_chains",
                        help="list the chains published by this site and exit")
    parser.add_argument("--datadir", help="override the destination data directory")
    parser.add_argument("--gateway", help="use only this IPFS gateway, e.g. https://ipfs.io/ipfs/")
    parser.add_argument("--no-daemon", action="store_true",
                        help="ignore a local IPFS daemon and use gateways")
    parser.add_argument("--tmp", default=os.path.join(os.getcwd(), "chainstrap-parts"),
                        help="where to keep downloaded parts (default: ./chainstrap-parts)")
    parser.add_argument("--keep", action="store_true", help="keep the downloaded parts")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would happen, download nothing")
    parser.add_argument("--yes", "-y", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--source", default=DOMAIN, help="ChainStrap site to read metadata from")
    args = parser.parse_args(argv)
    args.source = args.source if args.source.endswith("/") else args.source + "/"
    return parser, args


def main(argv=None):
    parser, args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.list_chains:
        codes = load_index(args.source)
        log("Chains published at %s\n" % args.source)
        for code in codes:
            config = load_config(args.source, code)
            nets = []
            for mode in ("mainnet", "testnet"):
                try:
                    meta = fetch_json("%s%s/%s-%s.json" % (args.source, code, code, mode))
                    nets.append("%s @ block %s" % (mode, "{:,}".format(meta.get("blocks", 0))))
                except Exception:
                    pass
            log("  %-6s %-14s %s" % (code, config.get("name", ""), "; ".join(nets) or "no snapshot"))
        log("\nRun: python3 getchain.py %s" % (codes[0] if codes else "RVN"))
        return 0

    if not args.chain:
        parser.print_help()
        return 1

    chain = args.chain.upper()
    mode = "testnet" if (args.testnet or args.network == "testnet") else "mainnet"

    config = load_config(args.source, chain)
    meta = load_metadata(args.source, chain, mode)
    parts = snapshot_parts(meta)
    datadir = resolve_datadir(config, mode, args.datadir)
    roots = allowed_roots(config)
    total_bytes = sum(p["bytes"] for p in parts if p.get("bytes")) or None

    log("")
    log("  Chain       %s (%s)" % (config.get("name", chain), chain))
    log("  Network     %s" % mode)
    log("  Height      %s" % "{:,}".format(meta.get("blocks", 0)))
    if meta.get("updated"):
        log("  Published   %s" % meta["updated"])
    log("  Snapshot    %s in %d part%s" % (human(total_bytes), len(parts),
                                           "" if len(parts) == 1 else "s"))
    log("  Destination %s" % datadir)
    log("  Folders     %s" % ", ".join(sorted(roots)))
    log("")

    if args.dry_run:
        for i, part in enumerate(parts, 1):
            log("[%d/%d] %s" % (i, len(parts), part["cid"]))
        log("\nDry run - nothing downloaded.")
        return 0

    if total_bytes:
        try:
            free = shutil.disk_usage(os.path.dirname(datadir) if not os.path.isdir(datadir)
                                     else datadir).free
            # Parts land on disk and are then expanded, so budget for both.
            needed = int(total_bytes * 2.6)
            if free < needed:
                log("Warning: about %s free where the data goes, but roughly %s is needed"
                    % (human(free), human(needed)))
                log("(Use --tmp to download the parts onto a different disk.)")
                if not confirm("Continue anyway?", args.yes):
                    return 1
        except OSError:
            pass

    existing = os.path.join(datadir, "blocks")
    if os.path.isdir(existing) and os.listdir(existing):
        log("There is already chain data in %s." % datadir)
        log("Extracting on top of it will replace matching files. Make sure the")
        log("client is CLOSED before continuing - a running node will corrupt.")
        if not confirm("Continue?", args.yes):
            return 1
    else:
        log("Make sure the client is closed before continuing.")
        if not confirm("Ready?", args.yes):
            return 1

    os.makedirs(datadir, exist_ok=True)
    os.makedirs(args.tmp, exist_ok=True)

    use_daemon = not args.no_daemon and not args.gateway and daemon_available()
    log("\nSource: %s\n" % ("local IPFS daemon on 127.0.0.1:5001" if use_daemon
                            else "public IPFS gateways over HTTPS"))

    started = time.time()
    for i, part in enumerate(parts, 1):
        path = fetch_part(part, i, len(parts), meta, args.tmp, args, use_daemon)
        log("  unpacking into %s" % datadir)
        extract(path, datadir, roots)
        if not args.keep:
            os.remove(path)
        log("")

    if not args.keep:
        try:
            os.rmdir(args.tmp)
        except OSError:
            pass

    log("Done in %s. %s %s data is in:" % (duration(time.time() - started), chain, mode))
    log("  %s" % datadir)
    log("")
    log("Start your client now; it will verify the data and sync the rest.")
    log("Add -reindex if you want it to re-scan everything from genesis.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\nInterrupted. Re-run the same command to resume.")
        sys.exit(130)

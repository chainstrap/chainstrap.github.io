#!/usr/bin/env python3
"""
ChainStrap - publish a snapshot of a synced chain to IPFS.

  ./savechain.py RVN              # mainnet
  ./savechain.py RVN --testnet    # testnet

Reads <CHAIN>/<CHAIN>-config.json for the data directory, the folders worth
packing and the RPC port, stops the node, zips those folders into parts, adds
each part to IPFS, and writes <CHAIN>/<CHAIN>-<network>.json - the file
index.html lists and getchain.py downloads.

Needs: a fully synced node with RPC enabled, and the `ipfs` command with a
running daemon.  Everything else is the Python standard library.
"""

import argparse
import base64
import datetime
import glob
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PART_SIZE = 2_000_000_000  # ~2 GB parts keep a failed transfer cheap
DEFAULT_GATEWAY = "https://ipfs.io/ipfs/"
CHUNK = 1 << 20


def log(msg=""):
    print(msg, flush=True)


def stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0 or unit == "TB":
            return "%.1f %s" % (n, unit)
        n /= 1024.0


# --------------------------------------------------------------------------
# config and paths
# --------------------------------------------------------------------------

def load_config(chain):
    path = os.path.join(SCRIPT_DIR, chain, "%s-config.json" % chain)
    if not os.path.exists(path):
        raise SystemExit("No config at %s" % path)
    with open(path) as handle:
        return json.load(handle)


def os_key():
    system = platform.system()
    return {"Windows": "windows", "Darwin": "darwin"}.get(system, "linux")


def expand(path):
    return os.path.expanduser(os.path.expandvars(path))


def resolve_datadir(config, mode, override):
    """Base data directory (no network subfolder) for this machine."""
    if override:
        return os.path.abspath(expand(override))
    key = os_key()
    dirs = config.get("datadir") or {}
    if key in dirs:
        return os.path.abspath(expand(dirs[key]))
    legacy = {"windows": "win_dir", "darwin": "mac_dir", "linux": "lin_dir"}[key]
    root, sub = config.get(legacy), config.get("subdir")
    if not root or not sub:
        raise SystemExit("Config has no data directory for %s." % platform.system())
    userdir = os.environ.get("APPDATA") if key == "windows" else os.path.expanduser("~")
    root = root.replace("%USERDIR%", userdir or os.path.expanduser("~"))
    if key == "linux" and not sub.startswith("."):
        sub = "." + sub
    return os.path.abspath(expand(os.path.join(root.replace("/", os.sep), sub)))


def network_dir(config, base, mode):
    """Where blocks/ and chainstate/ actually live for this network."""
    if mode == "mainnet":
        return base
    key = "%s_dir" % mode
    sub = config.get(key)
    if not sub:
        raise SystemExit("Config does not name a %s directory (%s)." % (mode, key))
    return os.path.join(base, sub)


def config_folders(config):
    folders = config.get("folders")
    if isinstance(folders, dict):
        folders = list(folders.keys())
    if not isinstance(folders, list) or not folders:
        folders = ["blocks", "blocks/index", "chainstate"]
    return folders


# --------------------------------------------------------------------------
# node RPC
# --------------------------------------------------------------------------

def rpc_credentials(config, base_dir, net_dir):
    """Env vars, then the chain's .conf, then the auth cookie the node writes."""
    user = os.environ.get("CHAINSTRAP_RPC_USER")
    password = os.environ.get("CHAINSTRAP_RPC_PASSWORD")
    if user and password:
        return user, password

    conf_name = config.get("conf_file")
    if conf_name:
        conf_path = os.path.join(base_dir, conf_name)
        if os.path.exists(conf_path):
            user = password = None
            with open(conf_path, errors="replace") as handle:
                for line in handle:
                    line = line.split("#", 1)[0].strip()
                    if line.startswith("rpcuser="):
                        user = line.split("=", 1)[1].strip()
                    elif line.startswith("rpcpassword="):
                        password = line.split("=", 1)[1].strip()
            if user and password:
                return user, password

    cookie = os.path.join(net_dir, ".cookie")
    if os.path.exists(cookie):
        with open(cookie) as handle:
            user, _, password = handle.read().strip().partition(":")
        if user and password:
            return user, password

    raise SystemExit(
        "No RPC credentials. Set CHAINSTRAP_RPC_USER and CHAINSTRAP_RPC_PASSWORD,\n"
        "or put rpcuser/rpcpassword in the chain's .conf, or let the node write "
        "its .cookie file.")


def rpc_call(port, auth, method, params=None, timeout=120):
    payload = json.dumps({"jsonrpc": "1.0", "id": "chainstrap",
                          "method": method, "params": params or []}).encode()
    token = base64.b64encode(("%s:%s" % auth).encode()).decode()
    req = Request("http://127.0.0.1:%d/" % port, data=payload,
                  headers={"Authorization": "Basic " + token,
                           "Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    if body.get("error"):
        raise RuntimeError(body["error"])
    return body.get("result")


def rpc_port_for(config, mode, override):
    if override:
        return override
    port = config.get("%s_rpc_port" % mode)
    if not port:
        raise SystemExit("Config has no %s_rpc_port." % mode)
    return int(port)


def wait_for_shutdown(port, auth, seconds):
    """Poll until the RPC port stops answering, so we never zip a live database."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            rpc_call(port, auth, "uptime", timeout=5)
        except (URLError, HTTPError, OSError, RuntimeError, ValueError):
            return True
        time.sleep(2)
    return False


# --------------------------------------------------------------------------
# packing
# --------------------------------------------------------------------------

def collect_files(net_dir, folders):
    """Relative paths of every file in the configured folders, sorted."""
    found = []
    for folder in folders:
        pattern = os.path.join(net_dir, folder.replace("/", os.sep), "*")
        for path in glob.glob(pattern):
            if os.path.isfile(path):
                rel = os.path.relpath(path, net_dir).replace(os.sep, "/")
                found.append(rel)
    found = sorted(set(found))
    if not found:
        raise SystemExit("No files found under %s in %s" % (folders, net_dir))
    return found


def build_parts(chain, mode, net_dir, files, outdir, max_size):
    """Zip `files` into parts no larger than roughly `max_size`."""
    parts = []
    pending = list(files)
    index = 0
    raw_total = 0

    while pending:
        name = os.path.join(outdir, "%s-%s-%d.zip" % (chain, mode, index))
        packed = 0
        log("  part %d -> %s" % (index, os.path.basename(name)))
        with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            while pending:
                rel = pending[0]
                source = os.path.join(net_dir, rel.replace("/", os.sep))
                if not os.path.exists(source):  # node may have rotated it away
                    pending.pop(0)
                    continue
                raw_total += os.path.getsize(source)
                archive.write(source, rel)
                pending.pop(0)
                packed += 1
                if archive.fp.tell() >= max_size:
                    break
        size = os.path.getsize(name)
        log("    %d files, %s" % (packed, human(size)))
        parts.append({"path": name, "bytes": size})
        index += 1

    log("  %s of chain data in %d part%s (%s)"
        % (human(raw_total), len(parts), "" if len(parts) == 1 else "s",
           human(sum(p["bytes"] for p in parts))))
    return parts


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# IPFS
# --------------------------------------------------------------------------

def ipfs_binary(override):
    found = override or shutil.which("ipfs")
    if not found:
        raise SystemExit("`ipfs` not found on PATH. Install IPFS (kubo) and start the daemon.")
    return found


def ipfs_add(binary, path):
    """Add a file and pin it. Returns the CID."""
    result = subprocess.run([binary, "add", "-Q", "--pin=true", path],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("ipfs add failed for %s:\n%s" % (path, result.stderr.strip()))
    cid = result.stdout.strip().splitlines()[-1].strip()
    if not cid:
        raise SystemExit("ipfs add returned no CID for %s" % path)
    return cid


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def write_metadata(chain, mode, info, parts, gateway):
    payload = {
        "chain": chain,
        "mode": mode,
        "blocks": info.get("blocks"),
        "blockhash": info.get("bestblockhash"),
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "bytes": sum(p["bytes"] for p in parts),
        "parts": [{"cid": p["cid"], "bytes": p["bytes"], "sha256": p["sha256"]} for p in parts],
        # Kept so copies of getchain.py older than 2026-08 still work.
        "ipfs_hashes": [p["cid"] for p in parts],
        "baseurl": gateway,
    }
    out_dir = os.path.join(SCRIPT_DIR, chain)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s-%s.json" % (chain, mode))
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="savechain.py",
        description="Zip a synced chain's data, add it to IPFS and publish the metadata.")
    parser.add_argument("chain", help="chain code, e.g. RVN")
    parser.add_argument("network", nargs="?", choices=["mainnet", "testnet", "regtest"],
                        help="network (may also be given as --testnet)")
    parser.add_argument("--testnet", action="store_true")
    parser.add_argument("--regtest", action="store_true")
    parser.add_argument("--datadir", help="override the node's data directory")
    parser.add_argument("--rpc-port", type=int, help="override the RPC port")
    parser.add_argument("--part-size", type=int, default=DEFAULT_PART_SIZE,
                        help="maximum bytes per zip part (default ~2GB)")
    parser.add_argument("--outdir", default=SCRIPT_DIR, help="where to build the zip parts")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY,
                        help="gateway URL recorded in the metadata")
    parser.add_argument("--ipfs", help="path to the ipfs binary")
    parser.add_argument("--no-stop", action="store_true",
                        help="do not stop the node (only safe if it is already stopped)")
    parser.add_argument("--keep-zips", action="store_true", help="keep the zip parts")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be packed and exit")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    chain = args.chain.upper()
    mode = ("testnet" if args.testnet else
            "regtest" if args.regtest else
            args.network or "mainnet")

    config = load_config(chain)
    base_dir = resolve_datadir(config, mode, args.datadir)
    net_dir = network_dir(config, base_dir, mode)
    folders = config_folders(config)
    port = rpc_port_for(config, mode, args.rpc_port)

    if not os.path.isdir(net_dir):
        raise SystemExit("Data directory not found: %s" % net_dir)

    log("%s  %s %s" % (stamp(), chain, mode))
    log("  data     %s" % net_dir)
    log("  folders  %s" % ", ".join(folders))
    log("  rpc      127.0.0.1:%d" % port)

    auth = rpc_credentials(config, base_dir, net_dir)
    info = {}
    try:
        info = rpc_call(port, auth, "getblockchaininfo")
        log("  height   %s" % "{:,}".format(info.get("blocks", 0)))
        if info.get("initialblockdownload"):
            raise SystemExit("Node is still in initial block download - not publishing.")
        progress = info.get("verificationprogress")
        if progress is not None and progress < 0.9999:
            raise SystemExit("Node is only %.4f%% verified - not publishing."
                             % (progress * 100))
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit("Could not query the node over RPC: %s\n"
                         "Start it with -server and RPC credentials, or pass --no-stop "
                         "with --datadir if it is already stopped." % exc)

    files = collect_files(net_dir, folders)
    log("  files    %d" % len(files))

    if args.dry_run:
        log("\nDry run - nothing packed.")
        return 0

    if not args.no_stop:
        log("\n%s  Stopping the node..." % stamp())
        try:
            rpc_call(port, auth, "stop", timeout=30)
        except Exception as exc:
            log("  stop RPC returned: %s" % exc)
        if not wait_for_shutdown(port, auth, 180):
            raise SystemExit("Node still answering RPC after 3 minutes - aborting so the "
                             "database is not copied while in use.")
        time.sleep(5)  # let LevelDB finish flushing to disk
        log("  stopped")

    # Re-scan: the node rewrites files as it shuts down.
    files = collect_files(net_dir, folders)

    log("\n%s  Packing..." % stamp())
    os.makedirs(args.outdir, exist_ok=True)
    parts = build_parts(chain, mode, net_dir, files, args.outdir, args.part_size)

    binary = ipfs_binary(args.ipfs)
    log("\n%s  Adding to IPFS..." % stamp())
    for i, part in enumerate(parts, 1):
        part["sha256"] = sha256_of(part["path"])
        part["cid"] = ipfs_add(binary, part["path"])
        log("  [%d/%d] %s  %s" % (i, len(parts), part["cid"], human(part["bytes"])))

    path = write_metadata(chain, mode, info, parts, args.gateway)
    log("\n%s  Wrote %s" % (stamp(), path))

    if not args.keep_zips:
        for part in parts:
            os.remove(part["path"])

    log("Commit and push %s to publish it." % os.path.relpath(path, SCRIPT_DIR))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\nInterrupted.")
        sys.exit(130)

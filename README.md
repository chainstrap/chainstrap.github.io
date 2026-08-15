# ChainStrap

**[chainstrap.com](https://chainstrap.com)** — a portmanteau of Bootstrap and Blockchain.

This project lets blockchains bootstrap quickly. As blockchain data gets larger with more
transactions, the sync time for the core clients can be days or weeks. This makes it nearly
unusable, or at least forces a very high commitment level to get in and get started.

The purpose of this infrastructure is to provide a cross-platform way to download a compressed
version of the raw chain data. It is still up to the core clients to validate the data. It isn't
necessary for everyone to verify all the data. To fully verify, the core client checks every
transaction and every signature, including the merkle root in every block header, and that every
block header is properly chained together with a proof-of-work that matches the difficulty, all
the way from the genesis block. In a properly running chain, most nodes have done this.

### Scanning
This solution simply gives a new user the opportunity to quickly download compressed blockchain
data and put it in the right location. If the user wishes, they can `-reindex` to scan the entire
chain.

### Trust
Trust required? Yes — running this requires trust that the code will not take or replace the
`wallet.dat`. `getchain.py` is a single dependency-free file, and easy to analyze. It only writes
into the block/chainstate folders named in the chain's config, and refuses archive entries that
point anywhere else. Most core software can verify the blockchain from origin, so trust of the
*data* isn't necessary.

### Multiple blockchains
This will work for any number of blockchains. It is driven by a config file for the location, and
works for testnet or mainnet on any Bitcoin-like chain.

### IPFS
The data is stored on IPFS, so it requires that someone hold the data. It takes advantage of the
nature of IPFS for storing many copies for optimization of delivery. It also relies on IPFS for
the immutability of the data from its Content Id (hash).

### Cross-platform
`getchain.py` uses only the Python standard library, so it runs on Windows, Linux and Mac with no
`pip install` step. Python will need to be installed on Windows:
https://www.python.org/downloads/windows/

## Usage

```
curl -O https://chainstrap.com/getchain.py
python3 getchain.py --list            # chains available
python3 getchain.py RVN               # mainnet
python3 getchain.py RVN --testnet     # testnet
```

On Windows use `curl.exe -O ...` and `python getchain.py RVN`.

**Close the wallet/node first** — extracting under a running client corrupts its database.

Useful options:

| Option | What it does |
| --- | --- |
| `--list` | List published chains and their snapshot heights |
| `--dry-run` | Show the destination and parts, download nothing |
| `--datadir PATH` | Extract somewhere other than the default data directory |
| `--gateway URL` | Use one specific IPFS gateway |
| `--no-daemon` | Ignore a local IPFS daemon, use HTTPS gateways |
| `--tmp PATH` | Download the parts to another disk |
| `--keep` | Keep the downloaded parts after extracting |
| `--yes` | Don't prompt (for scripts) |

If an IPFS daemon is running on `127.0.0.1:5001` it is used and the daemon verifies content
hashes itself. Otherwise the parts come from public gateways over HTTPS, with resume on
interruption, and each part is checked against the SHA-256 recorded in its metadata.

## Usage to save a chain

Prerequisites:
* A fully synced node with RPC enabled (e.g. `ravend` or Raven-Qt with `-server`).
* IPFS (kubo) installed with the daemon running (`ipfs daemon` or IPFS Desktop).

```
git clone https://github.com/chainstrap/chainstrap.github.io.git
cd chainstrap.github.io
./savechain.py RVN --dry-run     # what it would pack, and from where
./savechain.py RVN               # stop node, zip, add to IPFS, write metadata
git commit -am 'Update chain' && git push
```

`savechain.py` refuses to publish a node that is still in initial block download. RPC credentials
come from `CHAINSTRAP_RPC_USER` / `CHAINSTRAP_RPC_PASSWORD`, else the chain's `.conf`, else the
`.cookie` file the node writes — no credentials live in this repo.

See [scripts/README.md](scripts/README.md) for running it daily from cron.

## Adding a chain

1. Create `<CODE>/<CODE>-config.json` — the data directory per OS, the testnet subfolder, the
   folders to pack, and the RPC ports. See [RVN/RVN-config.json](RVN/RVN-config.json).
2. Add `"<CODE>"` to [chains.json](chains.json).
3. Run `./savechain.py <CODE>` on a synced node.

The website reads those same files, so a new chain appears on
[chainstrap.com](https://chainstrap.com) with no code changes.

## Layout

| File | Purpose |
| --- | --- |
| `index.html` | The site — a single static page that builds the chain list in the browser |
| `chains.json` | Which chains this site publishes |
| `getchain.py` | Client script: download a snapshot and unpack it |
| `savechain.py` | Publisher script: pack a synced chain and add it to IPFS |
| `<CODE>/<CODE>-config.json` | Per-chain paths, folders and ports |
| `<CODE>/<CODE>-<network>.json` | Snapshot metadata: height, parts, CIDs, checksums |

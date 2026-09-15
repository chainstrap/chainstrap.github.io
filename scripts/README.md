# Automating savechain
* Create a bespoke SSH key for pushing the updated information to {chain}.{chain}-mainnet.json
* Use ```sudo crontab -e``` to add ```4 0 * * * /root/chainstrap.github.io/daily_RVN.sh``` to schedule a daily run.
* Set up heartbeat monitoring with UptimeRobot and modify the heartbeat URL.
* The daily run also unpins parts older than five days and garbage collects the IPFS repo, so disk
  use stays flat. On a node that published before that existed, run
  `./savechain.py RVN --prune-only --adopt-history` once to catch up on the old final parts.

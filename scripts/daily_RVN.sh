#!/bin/bash
# Use:
# sudo crontab -e
# Add:
# 4 0 * * * /root/chainstrap.github.io/scripts/daily_RVN.sh

cd /root/chainstrap.github.io
./savechain.py RVN >> savechain.log
git add RVN/RVN-mainnet.json
git commit -m 'Update chain'
git push
wget --spider https://heartbeat.uptimerobot.com/m787981208-1a26bdea079ab569c84c73b62af23ebde7d9d081
ravend -daemon


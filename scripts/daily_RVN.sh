#!/bin/bash
# Use:
# sudo crontab -e
# Add:

# Runs this daily script 
# 4 0 * * * /root/chainstrap.github.io/scripts/daily_RVN.sh >> /root/chainstrap.github.io/cron.out

#Checks to make sure ipfs is running and then provides heartbeat
# * * * * * /snap/bin/ipfs diag sys && wget --spider https://heartbeat.uptimerobot.com/m788009529-fe47d77c931ef22954680f9b630b562d5eacf038

cd /root/chainstrap.github.io
./savechain.py RVN &>> savechain.log
git add RVN/RVN-mainnet.json
git commit -m 'Update chain'
git push
wget --spider https://heartbeat.uptimerobot.com/m787981208-1a26bdea079ab569c84c73b62af23ebde7d9d081
ravend -daemon


#!/usr/bin/env python3
import sys
from os.path import basename 
from os import path
import os
import zipfile
import platform
try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen
import json


if (len(sys.argv) >= 2):
	chain = sys.argv[1]
else:
	chain = "RVN"

if (len(sys.argv) >= 3):
	if sys.argv[2] == 'mainnet' or sys.argv[2] == 'testnet':
		mode = sys.argv[2]
	else:
		help()
else:
	mode = "mainnet"

if (platform.system() == "Darwin"):
	datadir = os.path.expanduser("~/Library/Application Support/Raven/")
if (platform.system() == "Linux"):
	datadir = os.path.expanduser("~/.raven/")
if (platform.system() == "Windows"):
	datadir = path.expandvars(r'%APPDATA%')
	datadir += os.sep + Raven + os.sep

print(datadir)
# current directory
script_dir = path.dirname(path.abspath(__file__)) + os.sep

def help():
	print('python getchain.py [coin] [mode]')
	print('  coin is coin code like RVN - default is RVN')
	print("  mode should be mainnet or testnet - default is mainnet")
	exit(0)

def get_jsonparsed_data(url):
    response = urlopen(url)
    data = response.read().decode("utf-8")
    return json.loads(data)

def get_metadata(coin, mode):
	return(get_jsonparsed_data('https://chainstrap.github.io/' + coin + '/' + coin + '-' + mode + '.json' ))


def get_from_ipfs(hash):
    print('Getting ' + hash + ' from IPFS...')
    import ipfsapi
    try:
    	api = ipfsapi.connect('127.0.0.1', 5001)
    except:
    	print("Error getting from ipfs.  Make sure you run")
    	print("  ipfs daemon")
    	exit(-1)
    return(api.get(hash))

def extract_zip_file(directory_to_extract_to, path_to_zip_file):
	import zipfile
	zip_ref = zipfile.ZipFile(path_to_zip_file, 'r')
	zip_ref.extractall(directory_to_extract_to)
	zip_ref.close()    
  
chaindata = get_metadata(chain, mode)
print(chaindata)
if chaindata['mode'] == 'testnet':
	datadir += 'testnet6' + os.sep   #Very RVN specific
get_from_ipfs(chaindata['ipfs_hash'])
print("Extracting " + chain + ' data to ' + datadir)
extract_zip_file(datadir, chaindata['ipfs_hash'])
if (chaindata['ipfs_hash'][0:2] == 'Qm' and len(chaindata['ipfs_hash']) == 46):
	os.remove(chaindata['ipfs_hash'])

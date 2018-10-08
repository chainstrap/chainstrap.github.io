#!/usr/bin/env python3

domain = 'https://chainstrap.github.io/'

import sys
from os.path import basename 
from os import path
import os
import zipfile
import platform
try:
	import ipfsapi
except ImportError:
	print("Requires ipfsapi")
	print("pip install ipfs")
	exit(-1)

try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen
import json

def show_help():
	print('python getchain.py [coin] [mode]')
	print('  coin is coin code like RVN - default is RVN')
	print("  mode should be mainnet or testnet - default is mainnet")
	exit(0)

#Add OS specific folder separator
def add_sep(dir):
	if (dir[-1] != os.sep):
		dir = dir + os.sep
	return(dir)

def get_datadir(config, mode):
	userdir = os.path.expanduser('~')
	if (platform.system() == "Darwin"):
		datadir = add_sep(config['mac_dir']) + add_sep(config['subdir']) 
	if (platform.system() == "Linux"):
		datadir = add_sep(config['lin_dir']) + '.' + add_sep(config['subdir'])
	if (platform.system() == "Windows"):
		userdir = path.expandvars(r'%APPDATA%')
		datadir += config['lin_dir'] + add_sep(config['subdir'])
	datadir = datadir.replace(R'%USERDIR%', userdir)
	if mode == 'testnet':
		datadir += add_sep(config['testnet_dir'])
	return(datadir)

# current directory
#script_dir = path.dirname(path.abspath(__file__)) + os.sep

def get_jsonparsed_data(url):
    response = urlopen(url)
    data = response.read().decode("utf-8")
    return json.loads(data)

def get_metadata(coin, mode):
	return(get_jsonparsed_data(domain + coin + '/' + coin + '-' + mode + '.json' ))

def get_chain_config(coin):
	return(get_jsonparsed_data(domain + coin + '/' + coin + '-config.json' ))

def get_from_ipfs(hash):
    print('Getting ' + hash + ' from IPFS...')
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

if (len(sys.argv) >= 2):
	chain = sys.argv[1]
else:
	show_help()

if (len(sys.argv) >= 3):
	if sys.argv[2] == 'mainnet' or sys.argv[2] == 'testnet':
		mode = sys.argv[2]
	else:
		show_help()
else:
	mode = "mainnet"

chain_config = get_chain_config(chain)
datadir = get_datadir(chain_config, mode)
chaindata = get_metadata(chain, mode)
print(chaindata)

get_from_ipfs(chaindata['ipfs_hash'])
print("Extracting " + chain + ' data to ' + datadir)
extract_zip_file(datadir, chaindata['ipfs_hash'])
if (chaindata['ipfs_hash'][0:2] == 'Qm' and len(chaindata['ipfs_hash']) == 46):
	os.remove(chaindata['ipfs_hash'])

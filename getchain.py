#!/usr/bin/env python3

domain = 'https://chainstrap.com/'

import sys
from os.path import basename 
from os import path
import os
import zipfile
import platform
import datetime
from urllib.request import urlopen, Request
try:
	import ipfshttpclient
except ImportError:
	print("Requires ipfshttpclient")
	print("pip install ipfshttpclient")
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
    print("Getting: " + url)
    r = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    data = urlopen(r).read().decode("utf-8")
    #data = response.read()  #
    return json.loads(data)

def get_metadata(coin, mode):
	return(get_jsonparsed_data(domain + coin + '/' + coin + '-' + mode + '.json' ))

def get_chain_config(coin):
	return(get_jsonparsed_data(domain + coin + '/' + coin + '-config.json' ))

def print_time():
    ct = datetime.datetime.now()
    print("Time: ", ct)

def get_from_ipfs(hash):
    print('Getting ' + hash + ' from IPFS...')
    #try:
    client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')  # Connects to: /dns/localhost/tcp/5001/http

    	#api = ipfsapi.connect('127.0.0.1', 5001)
    #except:
    #	print("Error getting from ipfs.  Make sure you run")
    #	print("  ipfs daemon")
    #	exit(-1)
    return(client.get(hash))

def wget_from_ipfs(baseurl, ipfshash):
    import wget
    print("wget: " + baseurl+ipfshash)
    wget.download(baseurl+ipfshash, ipfshash) 

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

for ipfshash in chaindata['ipfs_hashes']:
    print_time()
    #wget_from_ipfs(chaindata['baseurl'], ipfshash)
    get_from_ipfs(ipfshash)
    print_time()
    print("Extracting " + chain + ' data to ' + datadir)
    extract_zip_file(datadir, ipfshash)
    print_time()
    if (ipfshash[0:2] == 'Qm' and len(ipfshash) == 46):
	    os.remove(ipfshash)

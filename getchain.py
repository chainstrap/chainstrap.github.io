#!/usr/bin/env python3
import sys
from os.path import basename 
from os import path
import os
import json
import zipfile
import platform

chain = "RVN"

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

def get_metadata():
	with open(script_dir + chain + ".json") as json_data:
		dta = json.load(json_data)
	return(dta)


def get_from_ipfs(hash):
    print("Adding to IPFS")
    import ipfsapi
    api = ipfsapi.connect('127.0.0.1', 5001)
    return(api.get(hash))

def extract_zip_file(directory_to_extract_to, path_to_zip_file):
	import zipfile
	zip_ref = zipfile.ZipFile(path_to_zip_file, 'r')
	zip_ref.extractall(directory_to_extract_to)
	zip_ref.close()    
  
chaindata = get_metadata()
print(chaindata)
if chaindata['mode'] == 'testnet':
	datadir += 'testnet6' + os.sep
get_from_ipfs(chaindata['ipfs_hash'])
extract_zip_file(datadir, chaindata['ipfs_hash'])

#!/usr/bin/env python3
import sys
from os.path import basename 
from os import path
import os
import json
import zipfile
import glob
import time

chain = "RVN"
#default is mainnet
rpc_port = 8766
datadir = '/Users/tron/Library/Application Support/Raven/'
mode = 'mainnet'

if (len(sys.argv) == 2):
	if (sys.argv[1] == 'testnet'):
		rpc_port = 18766
		datadir = '/Users/tron/Library/Application Support/Raven/testnet6/'
		mode = 'testnet'
	if (sys.argv[1] == 'regtest'):
		rpc_port = 18443
		datadir = '/Users/tron/Library/Application Support/Raven/regtest/'
		mode = 'regtest'

# current directory
script_dir = path.dirname(path.abspath(__file__)) + os.sep

#Set this information in your raven.conf file (in datadir, not testnet3)
rpc_user = 'rpcuser'
rpc_pass = 'rpcpass555'

def get_rpc_connection():
    from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
    connection = "http://%s:%s@127.0.0.1:%s"%(rpc_user, rpc_pass, rpc_port)
    rpc_conn = AuthServiceProxy(connection)
    return(rpc_conn)
    
rpc_connection = get_rpc_connection()

def getblockchaininfo():
    result = rpc_connection.getblockchaininfo()
    return(result)

def stop():
    result = rpc_connection.stop()
    return(result)

def get_file_list(file_dir):
	file_list=[]
	add_files(file_list, file_dir, "blocks", '*')
	add_files(file_list, file_dir, "chainstate", '*')
	add_files(file_list, file_dir, "assets", '*')
	return(file_list)

def add_files(list, dir, subfolder, spec):
	os.chdir(dir)
	files = glob.glob(subfolder + "/" + spec)
	for file in files:
		print(file)
		list.append(file)

def write_metadata(info):
	obj={}
	obj['blocks'] = info['blocks']
	obj['blockhash'] = info['bestblockhash']
	obj['ipfs_hash'] = info['ipfs_hash']
	obj['url'] = info['url']
	obj['chain'] = chain
	obj['mode'] = mode
	fp = open(script_dir + os.sep + chain + os.sep + chain + '-' + mode + ".json", "w")
	json.dump(obj, fp, indent=2)
	fp.close()

def add_to_ipfs(file):
    print("Adding to IPFS")
    import ipfsapi
    api = ipfsapi.connect('127.0.0.1', 5001)
    res = api.add(file)
    print(res)
    return(res['Hash'])

def create_zip(chain, file_dir, file_list):
    os.chdir(file_dir)
    zip_name = script_dir + '{0}.zip'.format(chain)
    print("Compressing " + str(len(file_list)) + " files.")
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED, True) as zip_archive:
        for fname in file_list:
            print(file_dir + " " + fname)
            zip_archive.write(file_dir+fname, fname)
    return(zip_name)

print("Getting chain info for " + chain + " on port " + str(rpc_port))
try:
	info = getblockchaininfo()
except:
	print("Make sure " + chain + " is running on " + mode)
	exit(-1)

stop()
sleep_seconds = 20
print("Sleep for " + str(sleep_seconds) + " to let client stop.")
time.sleep(sleep_seconds)
print(info)
file_list = get_file_list(datadir)
print(file_list)
zip_full_path = create_zip(chain + '-' + str(info['blocks']), datadir, file_list)
print("Adding " + zip_full_path)

info['ipfs_hash'] = add_to_ipfs(zip_full_path)
os.remove(zip_full_path)
info['url'] = 'https://cloudflare-ipfs.com/ipfs/' + info['ipfs_hash']
write_metadata(info)


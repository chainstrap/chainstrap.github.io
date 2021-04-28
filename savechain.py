#!/usr/bin/env python3
import sys
from os.path import basename 
from os import path
import os
import json
import zipfile
import glob
import time
import datetime
from urllib.request import urlopen, Request
import ipfshttpclient


DEBUG=True
MaxZipSize = 2000000000

try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen

chain = "RVN"
#default is mainnet
rpc_port = 8766
mode = 'mainnet'
datadir = '/Users/tron/Library/Application Support/Raven/'
domain = 'https://chainstrap.com/'

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

def get_jsonparsed_data(url):
	r = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
	data = urlopen(r).read().decode("utf-8")
	#data = response.read()  #
	return json.loads(data)

def get_file_list(file_dir):
	file_list=[]
	add_files(file_list, file_dir, "blocks", '*')
	add_files(file_list, file_dir, "blocks/index", '*')
	add_files(file_list, file_dir, "chainstate", '*')
	add_files(file_list, file_dir, "assets", '*')
	file_list.sort()
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
	obj['ipfs_hashes'] = info['ipfs_hashes']
	obj['baseurl'] = info['baseurl']
	obj['chain'] = chain
	obj['mode'] = mode
	fp = open(script_dir + os.sep + chain + os.sep + chain + '-' + mode + ".json", "w")
	json.dump(obj, fp, indent=2)
	fp.close()

def add_to_ipfs(file):
    print("Adding to IPFS")
    client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')  # Connects to: /dns/localhost/tcp/5001/http
    res = client.add(file)
    print(res)
    return(res['Hash'])

def get_chain_config(coin):
	url = domain + coin + '/' + coin + '-config.json'
	print(url)
	return(get_jsonparsed_data(url))

def create_zips(chain, file_dir, file_list):
	cnt = 0
	list_of_zips = []
	while(len(file_list) > 0):
		zipfile = create_zip(chain, file_dir, file_list, cnt)
		list_of_zips.append(zipfile)
		cnt = cnt + 1
	return(list_of_zips)

def create_zip(chain, file_dir, file_list, cnt):
    os.chdir(file_dir)
    file_count = 0
    cumulative_size = 0
    break_out = False
    zip_name = script_dir + '{0}-{1}.zip'.format(chain, cnt)
    print("Compressing " + str(len(file_list)) + " files.")
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED, True) as zip_archive:
        for fname in file_list:
            print(file_dir + fname)
            cumulative_size = cumulative_size + os.path.getsize(file_dir+fname)
            zip_archive.write(file_dir+fname, fname)
            file_count = file_count + 1
            if (os.path.getsize(zip_name) > MaxZipSize):
            	print("Splitting Zip - " + str(cnt))
            	print("Saved: " + str((cumulative_size - os.path.getsize(zip_name))))	
            	#Remove ones that have been zipped
            	del file_list[:file_count]
            	break_out = True
            	break
        if (break_out == False):
           del file_list[:file_count]
    return(zip_name)

def print_time():
    ct = datetime.datetime.now()
    print("Time: ", ct)

#print("adding Test")
#ipfs_hash = add_to_ipfs('requirements.txt')
#print("finished adding test")
#exit(0)

print_time()
print("Getting chain info for " + chain + " on port " + str(rpc_port))
try:
	info = getblockchaininfo()
except:
	print("Make sure " + chain + " is running on " + mode)
	#exit(-1)

chain_config = get_chain_config(chain)
datadir = get_datadir(chain_config, mode)

try:
	stop()
	sleep_seconds = 20
	print("Sleep for " + str(sleep_seconds) + " to let client stop.")
	time.sleep(sleep_seconds)
except:
	print("Could not stop " + chain)

print(info)
file_list = get_file_list(datadir)
print(file_list)
zip_full_path_list = create_zips(chain + '-' + str(info['blocks']), datadir, file_list)


print('Zip_full_path_list len:' + str(len(zip_full_path_list)))
print(zip_full_path_list)
ipfs_hashes = []
for zip_full_path in zip_full_path_list:
    print("Adding " + zip_full_path)
    ipfs_hash = add_to_ipfs(zip_full_path)
    ipfs_hashes.append(ipfs_hash)
    os.remove(zip_full_path)
info['ipfs_hashes'] = ipfs_hashes
info['baseurl'] = 'https://cloudflare-ipfs.com/ipfs/'
write_metadata(info)
print_time()


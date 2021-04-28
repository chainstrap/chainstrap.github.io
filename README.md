#  ChainStrap

This project lets blockchains bootstrap quickly.  As blockchain data gets larger with more transactions, the sync time for the core clients can be days or weeks.  This makes it nearly unusable, or at least forces a very high commitment level to get in and get started.  

The purpose of this infrastructure is to provide a cross-platform way to download a compressed version of the raw chain data.  It is still up to the core clients to validate the data.  It isn't necessary for everyone to verify all the data.  To fully verify the core client checks every transaction, and every signature, including the merkle root in every block header and that every block header properly chained together with a proof-of-work that matches the difficulty, all the way from the genesis block. In a properly running chain, most nodes have done this.  

### Scanning 
This solution simply gives a new user the opportunity to quickly download compressed blockchain data and put it in the right location.  If the user wishes, they can -reindex to scan the entire chain.

### Trust
Trust required?  Yes, running this requires trust that the code will not take or replace the wallet.dat.  The python code is very simple, and easy to analyze.  Most core software can verify the blockchain from origin, so trust of the data isn't necessary.

### Multiple blockchains
This will work for any number of blockchains.  It is set up to be driven from a config file for the location, and will work for testnet or mainnet on any Bitcoin-like chain.

### IPFS
The data is stored on IPFS, so it requires that someone hold the data.  It takes advantage of the nature of IPFS for storing many copies for optimization of delivery.  It also relies on IPFS for its immutability of the data from its Content Id (hash).

### Cross-platform
It uses Python which can be run on Windows, Linux, and Mac.  Python will need to be installed on Windows.  https://www.python.org/downloads/windows/

## Usage

### Linux
```
git clone https://github.com/chainstrap/chainstrap.github.io.git
cd chainstrap.github.io
apt install python3-pip
pip3 install -r requirements.txt
./getchain.py RVN
```

### Mac
```
git clone https://github.com/chainstrap/chainstrap.github.io.git
./getchain.py RVN
```

### Windows
Install python3 from https://www.python.org/downloads/windows/  
Install git from https://git-scm.com/download/win
```
git clone https://github.com/chainstrap/chainstrap.github.io.git
python3 getchain.py RVN
```


## Usage to Save a Chain
Prerequisites:
* A fully synced chain.
* A running RVN node (ravend or Raven-QT with -server)
* IPFS running as a daemon (```ipfs daemon``` or IPFS desktop)
```
git clone https://github.com/chainstrap/chainstrap.github.io.git
pip3 install -r requirements.txt
./savechain.py RVN
```

#  ChainStrap

This is a project that lets blockchains bootstrap quickly.  As blockchain data gets larger with more transactions, the sync time for the core clients can be days or weeks.  This makes it nearly unusable, or at least forces a very high commitment level to get in and get started.  

The purpose of this infrastructure is to provide a cross-platform way to download a compressed version of the raw chain data.  It is still up to the core clients to validate the data.  It isn't necessary for everyone to verify all the data.  To fully verify the core client checks every transaction, and every signature, to the merkle root in every block header and every block header properly chained together with a proof-of-work that matches the difficulty, all the way from the genesis block. In a properly running chain, the most nodes have done this.  

### Scanning 
This solution simply gives a new user the opportunity to quickly download compressed blockchain data and put it in the right location.  If the user wishes, they can -reindex to scan the entire chain.

### Trust
Trust required?  Yes, running this requires trust that the code will not take or replace the wallet.dat.  The code is very simple, and easy to analyze.

### Multiple blockchains
This will work for any number of blockchains.  It is set up to be driven from a config file for the location, and will work for testnet or mainnet on any Bitcoin-like chain.

### IPFS
The data is stored on IPFS, so it requires that someone hold the data.  It takes advantage of the nature of IPFS for storing many copies for optimization of delivery.  It also relies on IPFS for its immutability of the data from its Content Id (hash).



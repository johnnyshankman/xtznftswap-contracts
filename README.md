## HOW TO USE

The front end needs to always batch together two transactions.

### Proposing

Adds the proposal to the storage. Tezos tokens will be held custodialy until `accept_trade` or `cancel_trade` is called.

```
// for each token to trade
fa2Contract.methods.update_operators([{
  add_operator: {
    owner: account.address,
    operator: contract.address,
    token_id: token.id
  }
}])

// just one call after all that
// see tests for expected parameters
xtznftswapContract.methods.propose_trade(...)
```

### Accepting

Causes FA2 tokens and tezos to swap parties according to the proposal.

```
// for each token to trade
fa2Contract.methods.update_operators([{
  add_operator: {
    owner: account.address,
    operator: contract.address,
    token_id: token.id
  }
}])
// just one call to accept
xtznftswapContract.methods.accept_trade()
```

### Cancellation

Invalidates the trade proposal forever. Returns all tezos held custodially.

```
// just one call to cancel
xtznftswapContract.methods.cancel_trade(...)
// for each token you are no longer trading, for security purposes
fa2Contract.methods.update_operators([{
  remove_operator: {
    owner: account.address,
    operator: contract.address,
    token_id: token.id
  }
}])
```

### Orderbook Enigma Warning

Operators for an FA2 compliant token are *not* reset upon transfer.

This has fallout. If someone were to transfer/sell their token away, then buy it back, any operators they previously had set would come back to life. It's what I call the Orderbook Enigma because in the orderbook context, this means any valid trades you proposed are now active again unless manually cancelled.


## REFERENCE

Random FA2 Testnet Contracts:
* https://better-call.dev/ithacanet/KT1LofkgTJTpXvjscjgsZmPUSxP2iUimni8m/operations
* https://better-call.dev/jakartanet/KT1HT4ju6pYDsKVZc9zHSvS5DDkqSyLncTWe/interact/update_operators

In case you need some metadata to test with:
* https://better-call.dev/mainnet/big_map/23516/keys

SmartPy Reference IDE and Documentation:
* https://smartpy.io/ide
* https://smartpy.io/docs/

Inspiration:
* https://github.com/jagracar/tezos-smart-contracts/blob/main/python/contracts/fa2Contract.py

Faucet tutorial to get xtz on any test chain using CLI:
* https://coinsbench.com/tezos-faucet-how-to-get-free-tezos-for-hangzhou-test-blockchain-36fd188515b7

# Tezos FA2.1 Swapping/Barterinng Contracts

![Build](https://github.com/johnnyshankman/xtznftswap-contracts/actions/workflows/build.yml/badge.svg)

This repo uses SmartPy CLI to compile and unit test the core xtznftswap contract used by [https://xtznftswap.xyz](https://xtznftswap.xyz) and its vanity equivalent [https://tezosnft.trade](https://tezosnft.trade).

## Tests

To run tests be sure to have [SmartPy CLI](https://smartpy.io/docs/cli/) installed globally on your machine. After that you can use npm to run the tests with `npm run test`. Output for each test can be be found in `compile/` after running. Inspect the `log.html` file to visually see each step of the test and validate that things like Tezos balances of each account and internal contract storage are exactly what you expect.

### CI/Actions

Tests are ran automatically on every push to main and every push to a pull requested branch. This is to ensure we never merge broken code in `main` and never create a broken Github Release.

## Compilation

To run tests be sure to have [SmartPy CLI](https://smartpy.io/docs/cli/) installed globally on your machine. After that you can use npm to compile down the main contract using `npm run compile`. Output can be be found in `compile/` after running.

## Release

Bump the number in `package.json` accordingly in a pull request, get that merged, then run the `release.yml` Github Action. This will create a new Github Release automatically.

## How To Use Contract

The front end needs to always batch together two+ transactions.

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

This has fallout. If someone were to transfer/sell their token away, then buy it back, any operators they previously had set would come back to life. It's what I call the Orderbook Enigma because in the orderbook context, this means any valid trades you proposed are now active again unless manually cancelled. *Be very wary of this* and use `remove_operator` upon cancelling or accepting a trade.

### Current Deploys for Inspecting

Use the following mainnet and testnet contract to understand the Storage layout and interaction available publicly on chain.

* https://better-call.dev/mainnet/KT1Kbw5BZLW6Ju6XAmPJyjDuSMQKKBQHGzdi
* https://better-call.dev/ghostnet/KT1Lq11zqBKHhpmTgonr68zkNN8WyepyprZh


## References

### FA2 Minting Testnet Contract:
* https://better-call.dev/ghostnet/KT1KdrJroMbVfgQzhNSzFFtCCgB9yBm51ynG/interact/update_operators

### SmartPy Reference IDE and Documentation:
* https://smartpy.io/ide
* https://smartpy.io/docs/

### Inspiration:
* https://github.com/jagracar/tezos-smart-contracts/blob/main/python/contracts/fa2Contract.py

### Faucet tutorial to get xtz on any Testnet chain using CLI:
* https://coinsbench.com/tezos-faucet-how-to-get-free-tezos-for-hangzhou-test-blockchain-36fd188515b7

### In case you need some metadata to test with:
* https://better-call.dev/mainnet/big_map/23516/keys


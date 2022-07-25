"""Unit tests for the XTZFA2Swap contract class.
"""

import smartpy as sp


# the contract to test
swapContractKYC = sp.io.import_script_from_url(
    "file:contracts/xtzfa2swap.py")

# import two very common implementations of a FA2 token to test against
fa2Contract = sp.io.import_script_from_url(
    "file:fa2TestContract.py")
fa2Contract2 = sp.io.import_script_from_url(
    "file:fa2.py")


@sp.add_test(name = "Propose and accept a KYC trade")
def test_kyc_trade():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("Administrator")

    # Initialize the two FA2 contracts
    fa2_1 = fa2Contract2.FA2(
      administrator=sp.test_account("Administrator").address,
      metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=sp.test_account("Administrator").address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)
    fa2_1.transfer([
      sp.record(
          from_=sp.test_account("Administrator").address,
          txs=[sp.record(
            to_=sp.test_account("Alice").address,
            token_id=1,
            amount=1
          )]
      )]).run(
      sender=sp.test_account("Administrator").address
    )

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=1)) == 1)

    # FAIL: proposing a trade before we have set operator rights on tokens
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
        valid = False,
        exception = 'FA2_INSUFFICIENT_BALANCE'
    )

    # allow the swap contract to operate on the offered token
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # verify that admin still owns token 0 and alice token 1
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=1)) == 1)

    # propose a trade that requires the sender to send tezos
    # set acceptor to an address, signifying a KYC trade.
    # set 2 royalty addresses for each token to test auto 5% royalty splits.
    # NOTE: you must check log.html to validate the royalty fees transferred.
    #       in this test 0.025 to each royalty account in first trade
    #       in this test 0.050 to each royalty account in second trade
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([
                    sp.test_account("Johnny").address,
                    sp.test_account("Jane").address
                ]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([
                    sp.test_account("Bobby").address,
                    sp.test_account("Johnny").address
                ]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
    )

    # verify the contract holds 1tez + 5% in custody from proposer
    scenario.verify(swapC.balance == sp.tez(1))

    # verify that Alice still owns token 1 and Administrator still owns token 0
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=1)) == 1)

    # FAIL: can't accept the trade because contract doesnt have operator rights for the tokens
    swapC.accept_trade(0).run(
      valid=False,
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2),
    )

    # now allow the swap contract to operate on Alice's token
    fa2_1.update_operators(
      [sp.variant("add_operator", fa2_2.operator_param.make(
          owner=sp.test_account("Alice").address,
          operator=swapC.address,
          token_id=1))]).run(sender=sp.test_account("Alice").address)

    # FAIL: cant accept your own trade for somene else
    swapC.accept_trade(0).run(
      valid=False,
      exception='This can only be executed by the trade acceptor',
      sender=sp.test_account("Administrator").address
    )

    # FAIL: someone random cannot accept the trade on your behalf
    swapC.accept_trade(0).run(
      valid=False,
      exception='This can only be executed by the trade acceptor',
      sender=sp.test_account("Robert").address,
      amount=sp.tez(2),
    )

    # FAIL: you cant send wrong tez amount
    swapC.accept_trade(0).run(
      valid=False,
      exception = "The sent tez amount does not coincide trade proposal amount with 5% royalties",
      sender=sp.test_account("Alice").address,
      amount=sp.tez(1)
    )

    # transfer the token to someone else
    # hopefully they cant accept bc they arent the specified acceptor
    fa2_1.transfer([
      sp.record(
          from_=sp.test_account("Alice").address,
          txs=[sp.record(
            to_=sp.test_account("Robert").address,
            token_id=1,
            amount=1
          )]
      )]).run(
      sender=sp.test_account("Alice").address
    )

    # FAIL: you cant accept on someone elses behalf even with the correct tokens
    swapC.accept_trade(0).run(
      valid=False,
      exception = "This can only be executed by the trade acceptor",
      sender=sp.test_account("Rober").address,
      amount=sp.tez(2),
    )

    # transfer the token back to Alice so she can accept the proposed trade
    fa2_1.transfer([
      sp.record(
          from_=sp.test_account("Robert").address,
          txs=[sp.record(
            to_=sp.test_account("Alice").address,
            token_id=1,
            amount=1
          )]
      )]).run(
      sender=sp.test_account("Robert").address
    )

    # accept the trade
    # WARN: operators doesnt reset? that's crazy.
    # DEV: You must use the log.html file to ensure tezos was properly distributed to each account
    #      there is no way to check tezos balances of test accounts
    swapC.accept_trade(0).run(
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2),
    )

    # verify that now Alice has token 0 and Admin has token 1, they've swapped
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=1)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=0)) == 1)
    # verify the contract holds no balance of tez now
    scenario.verify(swapC.balance == sp.mutez(0))

    # FAIL: can't accept the same trade twice
    swapC.accept_trade(0).run(
      valid=False,
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2),
    )

    # FAIL: new owner needs to update operators before proposing will work again
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(0),
        mutez_amount2 = sp.tez(0),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([])
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([])
            )
        ]),
        proposer = sp.test_account("Alice").address,
        acceptor = sp.test_account("Administrator").address,
    )).run(
        sender = sp.test_account("Alice").address,
        amount = sp.tez(0),
        valid = False,
        exception = "FA2_INSUFFICIENT_BALANCE"
    )

@sp.add_test(name = "Propose and accept an anon trade")
def test_anon_trade():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("Administrator")

    # Initialize the two FA2 contracts using the other FA2 generator that is popular
    fa2_1 = fa2Contract2.FA2(
      administrator=sp.test_account("Administrator").address,
      metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=sp.test_account("Administrator").address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)
    fa2_1.transfer([
      sp.record(
          from_=sp.test_account("Administrator").address,
          txs=[sp.record(
            to_=sp.test_account("Alice").address,
            token_id=1,
            amount=1
          )]
      )]).run(
      sender=sp.test_account("Administrator").address
    )

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=1)) == 1)

    # FAIL: cannot propose trade before updating operators to allowlist this contract
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = swapC.address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
        valid = False,
        exception = 'FA2_INSUFFICIENT_BALANCE'
    )

    # allow the swap contract to operate on the offered tokens
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # verify that admin still owns token 0 and alice token 1
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=1)) == 1)

    # propose a trade that requires the sender to send tezos
    # set acceptor to the contract itself, signifying an anon trade.
    # set no royalty addresses, which should trigger no 5% royalty fees.
    # NOTE: you must check log.html to validate the royalty fee wasnt triggered.
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = swapC.address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
    )

    # verify the contract holds 1tez now in custody from proposer
    scenario.verify(swapC.balance == sp.tez(1))

    # verify that alice still owns token 1 and admin still owns token 0
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=1)) == 1)

    # allow the swap contract to operate on Alice's token
    fa2_1.update_operators(
      [sp.variant("add_operator", fa2_2.operator_param.make(
          owner=sp.test_account("Alice").address,
          operator=swapC.address,
          token_id=1))]).run(sender=sp.test_account("Alice").address)

    # FAIL: cant accept your own trade
    swapC.accept_trade(0).run(
      valid=False,
      amount=sp.tez(2),
      sender=sp.test_account("Administrator").address,
      exception='This can not be executed by the trade proposer'
    )

    # FAIL: someone random cannot accept the trade on your behalf
    swapC.accept_trade(0).run(
      valid=False,
      sender=sp.test_account("Robert").address,
      amount=sp.tez(2),
      exception='FA2_NOT_OPERATOR'
    )

    # FAIL: cant send wrong tez amount
    swapC.accept_trade(0).run(
      valid=False,
      sender=sp.test_account("Alice").address,
      amount=sp.tez(1),
      exception='The sent tez amount does not coincide trade proposal amount with 5% royalties'
    )

    # FAIL: DNE trade ID
    swapC.accept_trade(2).run(
      valid=False,
      sender=sp.test_account("Alice").address,
      amount=sp.tez(0),
      exception="The provided trade id doesn't exist"
    )

    # accept the trade
    swapC.accept_trade(0).run(
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2)
    )

    # verify that now Alice has token 0 and Admin has token 1, they've swapped
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=1)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=0)) == 1)
    # verify the contract holds no balance of tez now
    scenario.verify(swapC.balance == sp.mutez(0))

    # check you can't accept the trade again even with correct tezos
    swapC.accept_trade(0).run(
      valid=False,
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2),
      exception='Trade already executed'
    )


@sp.add_test(name = "Propose and accept your own anon trade")
def test_anon_weird_trade():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("Administrator")

    # Initialize the two FA2 contracts using the other FA2 generator that is popular
    fa2_1 = fa2Contract2.FA2(
      administrator=sp.test_account("Administrator").address,
      metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=sp.test_account("Administrator").address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the admin
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)

    # verify ownership
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=1)) == 1)

    # allow the swap contract to operate on the offered tokens
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=1))]).run(sender=sp.test_account("Administrator").address)

    # verify that admin still owns token 0 and alice token 1
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=1)) == 1)

    # propose an anon trade
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(0),
        mutez_amount2 = sp.tez(0),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = swapC.address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(0),
    )

    # verify that admin still owns token 0 and token 1
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=1)) == 1)

    # verify that you cannot accept it yourself even if you have the tokens
    swapC.accept_trade(0).run(
      sender=sp.test_account("Administrator").address,
      amount=sp.tez(0),
      valid=False,
      exception='This can not be executed by the trade proposer'
    )


@sp.add_test(name = "Propose and cancel a trade")
def test_cancel():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("fa2_admin")

    # Initialize the two FA2 contracts
    fa2_1 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(
        address=sp.test_account("Administrator").address,
        token_id=sp.nat(0),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://ccc")}).run(sender=fa2_admin)
    fa2_1.mint(
        address=sp.test_account("Alice").address,
        token_id=sp.nat(1),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://eee")}).run(sender=fa2_admin)

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Alice").address, sp.nat(1))].balance == 1)

    # allow the swap contract to operate on the offered token
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # verify that admin still owns token 0 and alice token 1
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Alice").address, sp.nat(1))].balance == 1)

    # propose a trade
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
    )

    # verify the contract holds 1tez now in custody from proposer
    scenario.verify(swapC.balance == sp.tez(1))

    # verify that alice still owns token 1 and admin still owns token 0
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Alice").address, sp.nat(1))].balance == 1)

    # FAIL: cancelling the trade but sending money in the tx to the contract
    swapC.cancel_trade_proposal(0).run(
      valid=False,
      exception="The operation does not need tez",
      sender=sp.test_account("Administrator").address,
      amount = sp.tez(1),
    )

    # cancel the trade
    swapC.cancel_trade_proposal(0).run(
      sender=sp.test_account("Administrator").address,
    )

    # verify the contract holds no balance of tez now
    scenario.verify(swapC.balance == sp.mutez(0))

    # you cannot accept the trade bc proposer has cancelled/un-accepted
    swapC.accept_trade(0).run(
      valid=False,
      exception='Trade is not completely accepted',
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2)
    )

    # since contract still has operator rights, can re-propose an identical trade
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1)
    )

@sp.add_test(name = "Fail to propose bc you dont have the tokens")
def test_fail_propose():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("fa2_admin")

    # Initialize the two FA2 contracts
    fa2_1 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(
        address=sp.test_account("Administrator").address,
        token_id=sp.nat(0),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://ccc")}).run(sender=fa2_admin)
    fa2_1.mint(
        address=sp.test_account("Alice").address,
        token_id=sp.nat(1),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://eee")}).run(sender=fa2_admin)

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Alice").address, sp.nat(1))].balance == 1)

    # allow the swap contract to operate on the offered token
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # send the token from admin to robert *before* proposing
    # if you do this the test should fail because you have insufficient balance
    fa2_1.transfer([
        sp.record(
            from_=sp.test_account("Administrator").address,
            txs=[sp.record(
              to_=sp.test_account("Robert").address,
              token_id=0,
              amount=1
            )]
        )]).run(
        sender=sp.test_account("Administrator").address
      )

    # verify that admin still owns token 0 and alice token 1
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 0)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Robert").address, sp.nat(0))].balance == 1)

    # propose a trade that is not allowed because the sender doesn't own those tokens
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        valid = False,
        exception = 'Missing item in map',
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
    )


@sp.add_test(name = "Fail to accept a trade bc the proposer doesnt have the tokens anymore")
def test_fail_accept_lost_tokens():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("fa2_admin")

    # Initialize the two FA2 contracts
    fa2_1 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(
        address=sp.test_account("Administrator").address,
        token_id=sp.nat(0),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://ccc")}).run(sender=fa2_admin)
    fa2_1.mint(
        address=sp.test_account("Alice").address,
        token_id=sp.nat(1),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://eee")}).run(sender=fa2_admin)

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Alice").address, sp.nat(1))].balance == 1)

    # allow the swap contract to operate on the offered token
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # propose a trade that is not allowed because the sender doesn't own those tokens
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
    )

    # send the token from admin to robert *after* proposing
    fa2_1.transfer([
        sp.record(
            from_=sp.test_account("Administrator").address,
            txs=[sp.record(
              to_=sp.test_account("Robert").address,
              token_id=0,
              amount=1
            )]
        )]).run(
        sender=sp.test_account("Administrator").address
      )

    # allow the swap contract to operate on Alice's token
    fa2_1.update_operators(
      [sp.variant("add_operator", fa2_2.operator_param.make(
          owner=sp.test_account("Alice").address,
          operator=swapC.address,
          token_id=1))]).run(sender=sp.test_account("Alice").address)

    # you cannot accept the trade bc proposer no longer owns the tokens
    swapC.accept_trade(0).run(
      valid=False,
      exception='FA2_INSUFFICIENT_BALANCE',
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2)
    )

@sp.add_test(name = "Fail to accept a trade bc you are not the acceptor")
def test_fail_accept_not_acceptor():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("fa2_admin")

    # Initialize the two FA2 contracts
    fa2_1 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(
        address=sp.test_account("Administrator").address,
        token_id=sp.nat(0),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://ccc")}).run(sender=fa2_admin)
    fa2_1.mint(
        address=sp.test_account("Alice").address,
        token_id=sp.nat(1),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://eee")}).run(sender=fa2_admin)

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Alice").address, sp.nat(1))].balance == 1)

    # allow the swap contract to operate on the offered token
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # propose a trade that is not allowed because the sender doesn't own those tokens
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
    )

    # send the token from admin to robert *after* proposing
    fa2_1.transfer([
        sp.record(
            from_=sp.test_account("Administrator").address,
            txs=[sp.record(
              to_=sp.test_account("Robert").address,
              token_id=0,
              amount=1
            )]
        )]).run(
        sender=sp.test_account("Administrator").address
      )

    # allow the swap contract to operate on Alice's token
    fa2_1.update_operators(
      [sp.variant("add_operator", fa2_2.operator_param.make(
          owner=sp.test_account("Alice").address,
          operator=swapC.address,
          token_id=1))]).run(sender=sp.test_account("Alice").address)

    # you cannot accept the trade bc proposer no longer owns the tokens
    swapC.accept_trade(0).run(
      valid=False,
      exception='FA2_INSUFFICIENT_BALANCE',
      sender=sp.test_account("Alice").address,
      amount=sp.tez(2)
    )

@sp.add_test(name = "Fail to propose because bad trade proposals")
def test_fail_propose_bad_proposals():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("fa2_admin")

    # Initialize the two FA2 contracts
    fa2_1 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=fa2_admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(
        address=sp.test_account("Administrator").address,
        token_id=sp.nat(0),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://ccc")}).run(sender=fa2_admin)
    fa2_1.mint(
        address=sp.test_account("Alice").address,
        token_id=sp.nat(1),
        amount=sp.nat(1),
        metadata={"" : sp.utils.bytes_of_string("ipfs://eee")}).run(sender=fa2_admin)

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Administrator").address, sp.nat(0))].balance == 1)
    scenario.verify(fa2_1.data.ledger[(sp.test_account("Alice").address, sp.nat(1))].balance == 1)

    # allow the swap contract to operate on the offered token
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # propose a trade that is not allowed because the trade is invalid
    # it contains no tokens and no tez on either side
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(0),
        mutez_amount2 = sp.tez(0),
        tokens1 = sp.list(),
        tokens2 = sp.list(),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        valid = False,
        exception = "At least one FA2 token needs to be traded by proposer",
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(0),
    )

    # propose a trade that is not allowed because the trade is invalid
    # it contains no offered tokens nor tez
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(0),
        mutez_amount2 = sp.tez(1),
        tokens1 = sp.list(),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        valid = False,
        exception = "At least one FA2 token needs to be traded by proposer",
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(0),
    )

    # propose a trade that is not allowed because the trade is invalid
    # it contains no receiving tokens nor tez
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(0),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list(),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        valid = False,
        exception = "At least one FA2 token needs to be traded by acceptor",
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
    )

    # propose a trade that is not allowed because the trade is invalid
    # the sent tez amount is incorrect
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(5),
        mutez_amount2 = sp.tez(1),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        valid = False,
        exception = "The sent tez amount does not coincide trade proposal amount with 5% royalties",
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(3),
    )

    # propose a trade that is not allowed because the trade is invalid
    # the two users are the same person
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(5),
        mutez_amount2 = sp.tez(1),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Administrator").address,
    )).run(
        valid = False,
        exception = "The users involved in the trade need to be different",
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(5),
    )

    # propose a trade that is not allowed because the trade is invalid
    # the proposer of the trade isnt the wallet that sent the tx
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(5),
        mutez_amount2 = sp.tez(1),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = sp.test_account("Alice").address,
    )).run(
        valid = False,
        exception = "This can only be executed by the trade proposer",
        sender = sp.test_account("Robert").address,
        amount = sp.tez(3),
    )

@sp.add_test(name = "Fail to propose bc denylisted")
def test_denylist_propose():
    # Create a scenario
    scenario = sp.test_scenario()

    # pull out the fa2_admin into a smaller var
    fa2_admin = sp.test_account("Administrator")

    # Initialize the two FA2 contracts using the other FA2 generator that is popular
    fa2_1 = fa2Contract2.FA2(
      administrator=sp.test_account("Administrator").address,
      metadata=sp.utils.metadata_of_url("ipfs://aaa"))
    fa2_2 = fa2Contract.FA2(
        config=fa2Contract.FA2_config(),
        admin=sp.test_account("Administrator").address,
        metadata=sp.utils.metadata_of_url("ipfs://bbb"))

    # Add the 2 fa2 contracts to the scenario
    scenario += fa2_1
    scenario += fa2_2

    # Instantiate the swap contract
    swapC = swapContractKYC.XTZFA2Swap(
      administrator=sp.test_account("Administrator").address,
    )

    # Add the swap contract to the scenario
    scenario += swapC # is equivalent to `scenario.register(swapC, show = True)`

    # Mint some tokens for the involved users, admin token 0 and alice token 1
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)
    fa2_1.mint(amount=sp.nat(1)).run(sender=sp.test_account("Administrator").address)
    fa2_1.transfer([
      sp.record(
          from_=sp.test_account("Administrator").address,
          txs=[sp.record(
            to_=sp.test_account("Alice").address,
            token_id=1,
            amount=1
          )]
      )]).run(
      sender=sp.test_account("Administrator").address
    )

    # verify that admin owns token 0 and alice owns token 1
    scenario.verify(fa2_1.total_supply(0) == 1)
    scenario.verify(fa2_1.total_supply(1) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Administrator").address, token_id=0)) == 1)
    scenario.verify(fa2_1.get_balance(sp.record(owner=sp.test_account("Alice").address, token_id=1)) == 1)

    # allow the swap contract to operate on the offered tokens
    fa2_1.update_operators(
        [sp.variant("add_operator", fa2_2.operator_param.make(
            owner=sp.test_account("Administrator").address,
            operator=swapC.address,
            token_id=0))]).run(sender=sp.test_account("Administrator").address)

    # add the fa2_1 contract to the denylist as denied
    swapC.modify_denylist(sp.record(
        contract = fa2_1.address,
        deny = True,
    )).run(
        sender = sp.test_account("Administrator").address,
    )

    # propose a trade using the fa2_1 tokens so that it fails
    swapC.propose_trade(sp.record(
        mutez_amount1 = sp.tez(1),
        mutez_amount2 = sp.tez(2),
        tokens1 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(0),
                royalty_addresses= sp.list([]),
            )
        ]),
        tokens2 = sp.list([
            sp.record(
                amount= sp.nat(1),
                fa2= fa2_1.address,
                id= sp.nat(1),
                royalty_addresses= sp.list([]),
            )
        ]),
        proposer = sp.test_account("Administrator").address,
        acceptor = swapC.address,
    )).run(
        sender = sp.test_account("Administrator").address,
        amount = sp.tez(1),
        valid = False,
        exception = 'The contract is on the denylist'
    )

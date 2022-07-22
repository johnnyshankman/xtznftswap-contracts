
import smartpy as sp

class XTZFA2Swap(sp.Contract):
    """This contract implements a trade/barter contract where users can swap
    FA2 tokens + tezos for other FA2 tokens + tezos. It also optionally allows
    you to specify trades with a specific recipient, a pseudo-KYC system.
    """

    TOKEN_TYPE = sp.TRecord(
        # The FA2 token's contract address
        fa2=sp.TAddress,
        # The FA2 token's id
        id=sp.TNat,
        # The quantity of that token to trade
        amount=sp.TNat,
        # Where to pay the 5% artist royalty
        royalty_addresses=sp.TList(sp.TAddress),
    ).layout(
      ("fa2", ("id", ("amount", "royalty_addresses"))
    ))

    TRADE_PROPOSAL_TYPE = sp.TRecord(
        # The first user involved in the trade
        proposer=sp.TAddress,
        # The second user involved in the trade
        # Set to this contract address to flag a trade as anonymous
        acceptor=sp.TAddress,
        # The first user's mutez amount to trade
        mutez_amount1=sp.TMutez,
        # The second user's mutez amount to trade
        mutez_amount2=sp.TMutez,
        # The first user's list of FA2 tokens to trade
        tokens1=sp.TList(TOKEN_TYPE),
        # The second user's list of FA2 tokens to trade
        tokens2=sp.TList(TOKEN_TYPE)
      ).layout(
          ("proposer", ("acceptor", ("mutez_amount1", ("mutez_amount2", ("tokens1", "tokens2")
      )))))

    def __init__(self):
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            trades=sp.TBigMap(sp.TNat, sp.TRecord(
                proposer_accepted=sp.TBool,
                acceptor_accepted=sp.TBool,
                executed=sp.TBool,
                proposal=XTZFA2Swap.TRADE_PROPOSAL_TYPE)),
            counter=sp.TNat,
            metadata=sp.TBigMap(sp.TString, sp.TBytes)))

        # Initialize the contract storage
        self.init(
            trades=sp.big_map(), # not passed in
            counter=0, # not passed in
            metadata=sp.big_map(), # not passed in
        )

        # Build TZIP-016 contract metadata
        # This is helpful to get the off-chain information in JSON format
        contract_metadata = {
            "name": "XTZFA2Swap",
            "description" : "A contract for securely and trustlessly trading any bundle of FA2 tokens & Tezos for another bundle of FA2 tokens & Tezos. The acceptor of the trade can be specified, or left open-ended for anyone to accept. Simply add this contract as an operator for your tokens, then propose or accept any trades involving those tokens. After cancelling a propsoal, it is suggested that you remove this contract as an operator of the involved tokens.",
            "version": "v1.0.0",
            "authors": ["White Lights <https://twitter.com/iamwhitelights>"],
            "homepage": "https://xtznftswap.io",
            "source": {
                "tools": ["SmartPy 0.11.1"],
                "location": "https://github.com/johnnyshankman/xtznftswap-contracts/"
            },
            "interfaces": ["TZIP-016"],
            "views": [],
        }
        self.init_metadata("contract_metadata", contract_metadata)

    def check_is_proposer(self, trade_proposal):
        """Checks that the address that called the entry point is
        the user who proposed the trade
        """
        sp.verify((sp.sender == trade_proposal.proposer),
                  message="This can only be executed by the trade proposer")

    def check_is_not_proposer(self, trade_proposal):
        """Checks that the address that called the entry point is
        NOT the user who proposed the trade
        """
        sp.verify((sp.sender != trade_proposal.proposer),
                  message="This can not be executed by the trade proposer")

    def check_is_acceptor(self, trade_proposal):
        """Checks whether the address that called the entry point is a
        user who can accept the trade. If the acceptor is this contract's
        address, anyone can accept the trade and we return true always.
        """
        sp.verify(((sp.sender == trade_proposal.acceptor) | (sp.self_address == trade_proposal.acceptor)),
                  message="This can only be executed by the trade acceptor")

    def check_no_tez_transfer(self):
        """Checks that no tezos were transferred in the operation.
        """
        sp.verify(sp.amount == sp.tez(0),
                  message="The operation does not need tez")

    def check_is_not_acceptor_accepted(self, trade_proposal):
        """Checks that the acceptor has not already accepted the trade
        """
        sp.verify(~trade.acceptor_accepted,
                    message="The trade is already accepted")

    def check_trade_completely_accepted(self, trade):
        """Checks the trade is accepted by both parties
        """
        sp.verify((trade.proposer_accepted == True) & (trade.acceptor_accepted == True),
                  message="Trade is not completely accepted")

    def check_trade_not_executed(self, trade_id):
        """Checks that the trade id corresponds to an existing trade that has
        not been executed.
        """
        # Check that the trade id is present in the trades big map
        sp.verify(self.data.trades.contains(trade_id),
                  message="The provided trade id doesn't exist")

        # Check that the trade was not executed before
        sp.verify(~self.data.trades[trade_id].executed,
                  message="Trade already executed")


    @sp.entry_point
    def propose_trade(self, trade_proposal):
        """Proposes a trade between two users.
        """
        # Define the input parameter data type
        sp.set_type(trade_proposal, XTZFA2Swap.TRADE_PROPOSAL_TYPE)

        # Check that the trade proposal comes from proposer
        self.check_is_proposer(trade_proposal)

        # Check that the two involved users are not the same wallet
        sp.verify(trade_proposal.proposer != trade_proposal.acceptor,
                  message="The users involved in the trade need to be different")

        # Check there is an FA2 token on each side of the trade
        sp.verify(sp.len(trade_proposal.tokens1) > 0, message="At least one FA2 token needs to be traded by proposer")
        sp.verify(sp.len(trade_proposal.tokens2) > 0, message="At least one FA2 token needs to be traded by acceptor")

        # Check that the tezos passed in to tx is the same as in the proposal
        sp.if trade_proposal.mutez_amount1 != sp.mutez(0):
            # Check that the sent tez sent to the contract coincides with
            # what was specified in the trade proposal
            sp.verify(sp.amount == trade_proposal.mutez_amount1,
                        message="The sent tez amount does not coincide trade proposal amount with 5% royalties")

        # Non-custodially ensure they own every token in the proposal
        sp.for token in trade_proposal.tokens1:
            # Checks they own all editions by sending them to the contract and back.
            # This is intentionally a no-op and two separate txs. Why? Some FA2 contracts dont
            # allow self sending, we cant use get_balance since it will not return the value
            # in the same entrypoint call, and balance_of is not guaranteed to be implemented.
            # This is our best option.
            self.fa2_transfer(
                fa2=token.fa2,
                from_=sp.sender,
                to_=sp.self_address,
                token_id=token.id,
                token_amount=token.amount)
            self.fa2_transfer(
                fa2=token.fa2,
                from_=sp.self_address,
                to_=sp.sender,
                token_id=token.id,
                token_amount=token.amount)

        # Update the trades order book bigmap with the new trade information
        # NOTE: By default, you're considered to have accepted your own trade
        self.data.trades[self.data.counter] = sp.record(
            proposer_accepted=True,
            acceptor_accepted=False,
            executed=False,
            proposal=trade_proposal)

        # Increase the trade id counter for next proposal
        self.data.counter += 1

    @sp.entry_point
    def accept_trade(self, trade_id):
        """Accepts a trade.
        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is the trade acceptor and not the proposer
        trade = self.data.trades[trade_id]
        self.check_is_acceptor(trade.proposal)
        self.check_is_not_proposer(trade.proposal)

        # Check that the user didn't accept the trade before
        sp.verify(~trade.acceptor_accepted,
                    message="The trade is already accepted")

        # Accept the trade as acceptor
        trade.acceptor_accepted = True

        sp.if trade.proposal.mutez_amount2 != sp.mutez(0):
            # Check that the sent tez coincides with what was specified in the trade proposal
            sp.verify(sp.amount == trade.proposal.mutez_amount2,
                        message="The sent tez amount does not coincide trade proposal amount with 5% royalties")

        # Triple check the trade is accepted on both sides
        self.check_trade_completely_accepted(trade)

        # Set the trade as executed and begin executing trade behavior
        trade.executed = True

        # Help calculate royalty fee and how many accounts to split it between
        royalties1 = sp.mutez(0)
        royaltyDenom1 = 0
        royaltyDenom1Local = sp.local('royaltyDenom1Local', royaltyDenom1)
        royalties2 = sp.mutez(0)
        royaltyDenom2 = 0
        royaltyDenom2Local = sp.local('royaltyDenom2Local', royaltyDenom2)

        # Find sum of all royalty addresses to use as denominator later for splits
        sp.for token in trade.proposal.tokens1:
            royaltyDenom1Local.value = royaltyDenom1Local.value + sp.len(token.royalty_addresses)
        # Transfer the locked tez from ESCROW/proposer to acceptor if there is tez
        sp.if ((royaltyDenom1Local.value > 0) & (trade.proposal.mutez_amount1 != sp.mutez(0))):
            # Calculate 5% royalties for acceptor side
            royalties1 = sp.split_tokens(trade.proposal.mutez_amount1, 1, 20)
            # Send proposed trade amount to user minus the 5% royalty fee
            sp.send(sp.sender, (trade.proposal.mutez_amount1 - royalties1))
        sp.else:
            sp.send(sp.sender, trade.proposal.mutez_amount1)

        # Find sum of all royalty addresses to use as denominator later for splits
        sp.for token in trade.proposal.tokens2:
            royaltyDenom2Local.value = royaltyDenom2Local.value + sp.len(token.royalty_addresses)
        # Transfer this tx's tez from acceptor to proposer if there is tez
        sp.if ((royaltyDenom2Local.value > 0) & (trade.proposal.mutez_amount2 != sp.mutez(0))):
            # Calculate 5% royalties for acceptor side
            royalties2 = sp.split_tokens(trade.proposal.mutez_amount2, 1, 20)
            # Send proposed trade amount to user minus the 5% royalty fee
            sp.send(trade.proposal.proposer, (trade.proposal.mutez_amount2 - royalties2))
        sp.else:
            sp.send(trade.proposal.proposer, (trade.proposal.mutez_amount2))

        # Transfer proposer's tokens to acceptor
        sp.for token in trade.proposal.tokens1:
            # transfer FA2
            self.fa2_transfer(
                fa2=token.fa2,
                from_=trade.proposal.proposer,
                to_=sp.sender,
                token_id=token.id,
                token_amount=token.amount)
            # Give every royalty address its cut of the 5% royalty
            sp.for royalty_address in token.royalty_addresses:
                royaltyCut = sp.split_tokens(royalties1, 1, royaltyDenom1Local.value)
                sp.send(royalty_address, royaltyCut)

        # Transfer acceptor's tokens to proposer
        sp.for token in trade.proposal.tokens2:
            # transfer FA2
            self.fa2_transfer(
                fa2=token.fa2,
                from_=sp.sender,
                to_=trade.proposal.proposer,
                token_id=token.id,
                token_amount=token.amount)
            # Give every royalty address its cut of the 5% royalty
            sp.for royalty_address in token.royalty_addresses:
                royaltyCut = sp.split_tokens(royalties2, 1, royaltyDenom2Local.value)
                sp.send(royalty_address, royaltyCut)

    @sp.entry_point
    def cancel_trade_proposal(self, trade_id):
        """Cancels a proposed trade from proposer by giving back tez and
           not accepting the trade. Ensures the trade is valid first.
        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is the proposer
        trade = self.data.trades[trade_id]
        self.check_is_proposer(trade.proposal)

        # Check that the user accepted the trade before
        sp.verify(trade.proposer_accepted,
                    message="The trade was not accepted before")

        # Change the status to not accepted
        trade.proposer_accepted = False

        # Transfer the locked tez back to the proposer
        sp.if trade.proposal.mutez_amount1 != sp.mutez(0):
            sp.send(sp.sender, trade.proposal.mutez_amount1)


    def fa2_transfer(self, fa2, from_, to_, token_id, token_amount):
        """Transfers a number of editions of a FA2 token between two addresses.
        """
        # Get a handle to the FA2 token transfer entry point
        c = sp.contract(
            t=sp.TList(
                sp.TRecord(
                    from_=sp.TAddress,
                    txs=sp.TList(
                        sp.TRecord(
                            to_=sp.TAddress,
                            token_id=sp.TNat,
                            amount=sp.TNat).layout(("to_", ("token_id", "amount")))
                        )
                    )
                ),
            address=fa2,
            entry_point="transfer").open_some()

        # Transfer the FA2 token editions to the new address
        sp.transfer(
            arg=sp.list([sp.record(
                from_=from_,
                txs=sp.list([sp.record(
                    to_=to_,
                    token_id=token_id,
                    amount=token_amount)]))]),
            amount=sp.mutez(0),
            destination=c)


# Add a compilation target initialized to some address as the contract manager
sp.add_compilation_target("xtznftswap", XTZFA2Swap())

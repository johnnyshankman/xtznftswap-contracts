
import smartpy as sp

class XTZFA2Swap(sp.Contract):
    """This contract implements a trade/barter contract where users can swap
    FA2 tokens + tezos for other FA2 tokens + tezos. It also optionally allows
    you to specify trades with a specific recipient, a pseudo-KYC system.
    """

    TOKEN_TYPE = sp.TRecord(
        # The FA2 token contract address
        fa2=sp.TAddress,
        # The FA2 token id
        id=sp.TNat,
        # The quantity of that token to trade
        amount=sp.TNat
    ).layout(
      ("fa2", ("id", "amount")
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

    def check_is_acceptor(self, trade_proposal):
        """Checks whethere the address that called the entry point is
        the user who can accept the trade. If the acceptor is this contract's
        address, anyone can accept the trade so we return true indiscriminately.
        """
        sp.verify(((sp.sender == trade_proposal.acceptor) | (sp.self_address == trade_proposal.acceptor)),
                  message="This can only be executed by the trade acceptor")

    def check_no_tez_transfer(self):
        """Checks that no tezos were transferred in the operation.
        """
        sp.verify(sp.amount == sp.tez(0),
                  message="The operation does not need tez")

    def check_trade_completely_accepted(self, trade):
        """Checks that no tez were transferred in the operation.
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

        sp.verify(sp.len(trade_proposal.tokens1) > 0, message="At least one FA2 token needs to be traded by proposer")
        sp.verify(sp.len(trade_proposal.tokens2) > 0, message="At least one FA2 token needs to be traded by acceptor")

        # Loop over the first user token list
        sp.for token in trade_proposal.tokens1:
            # Check that they own all editions by sending to contract and back.
            # This is intentionally a no-op. This is intentionally two txs.
            # Why? Some contracts disallow self sending and get_balance is not
            # an option as it is async. off-chain checking of balance is also not
            # an option bc it is not guaranteed.
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

        # Update the trades bigmap with the new trade information
        self.data.trades[self.data.counter] = sp.record(
            proposer_accepted=False,
            acceptor_accepted=False,
            executed=False,
            proposal=trade_proposal)

        # Instantly accept the trade on your end, trade_id is current counter value
        self.accept_my_trade(self.data.counter)

        # Increase the trades counter so another can be proposed
        self.data.counter += 1

    def accept_my_trade(self, trade_id):
        """Accepts your own trade.
        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is the proposer
        trade = self.data.trades[trade_id]
        self.check_is_proposer(trade.proposal)

        # Check that the user didn't accept the trade before
        sp.verify(~trade.proposer_accepted,
                    message="The trade is already accepted")

        # Accept the trade
        trade.proposer_accepted = True

        # Check that the sent tez sent to the contract coincides with
        # what was specified in the trade proposal
        sp.verify(sp.amount == trade.proposal.mutez_amount1,
                    message="The sent tez amount does not coincide trade proposal amount")

    @sp.entry_point
    def accept_trade(self, trade_id):
        """Accepts a trade.
        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is the trade acceptor
        trade = self.data.trades[trade_id]
        self.check_is_acceptor(trade.proposal)

        # Check that the user didn't accept the trade before
        sp.verify(~trade.acceptor_accepted,
                    message="The trade is already accepted")

        # Accept the trade
        trade.acceptor_accepted = True

        # Check that the sent tez coincides with what was specified in the trade proposal
        sp.verify(sp.amount == trade.proposal.mutez_amount2,
                    message="The sent tez amount does not coincide trade proposal amount")

        # Triple check the trade is accepted on both sides
        self.check_trade_completely_accepted(trade)

        # Finish the trade
        self.execute_trade(trade_id)

    @sp.entry_point
    def cancel_trade_proposal(self, trade_id):
        """Cancels a proposed trade from proposer by giving back tez and not accepting the trade
        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is the proposer, only proposers can cancel a trade
        trade = self.data.trades[trade_id]
        self.check_is_proposer(trade.proposal)

        # Check that the user accepted the trade before
        sp.verify(trade.proposer_accepted,
                    message="The trade was not accepted before")

        # Change the status to not accepted
        trade.proposer_accepted = False

        # Transfer the locked tez back to the proposer who proposed the trade
        sp.if trade.proposal.mutez_amount1 != sp.mutez(0):
            sp.send(sp.sender, trade.proposal.mutez_amount1)

    def execute_trade(self, trade_id):
        """Executes a trade.
        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is one of the trade users
        trade = self.data.trades[trade_id]
        self.check_is_acceptor(trade.proposal)

        # Check that the two users accepted the trade
        sp.verify(trade.proposer_accepted & trade.acceptor_accepted,
                  message="One of the users didn't accept the trade")

        # Set the trade as executed
        trade.executed = True

        # Transfer the tez from this submitted tx from acceptor to proposer
        sp.if trade.proposal.mutez_amount2 != sp.mutez(0):
            sp.send(trade.proposal.proposer, trade.proposal.mutez_amount2)

        # Transfer the locked tez from the proposer to the acceptor
        sp.if trade.proposal.mutez_amount1 != sp.mutez(0):
            sp.send(sp.sender, trade.proposal.mutez_amount1)

        # Transfer acceptor's tokens to proposer
        sp.for token in trade.proposal.tokens2:
            self.fa2_transfer(
                fa2=token.fa2,
                from_=sp.sender,
                to_=trade.proposal.proposer,
                token_id=token.id,
                token_amount=token.amount)

        # Transfer proposer's tokens to acceptor
        sp.for token in trade.proposal.tokens1:
            self.fa2_transfer(
                fa2=token.fa2,
                from_=trade.proposal.proposer,
                to_=sp.sender,
                token_id=token.id,
                token_amount=token.amount)

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
sp.add_compilation_target("swap", XTZFA2Swap())

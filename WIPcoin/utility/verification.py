"""Provides verification helper methods."""

from utility.hash_util import hash_string_256, hash_block
from wallet import Wallet

class Verification:
    """A helper class which offer various static and class-based verification and validation methods."""
    @staticmethod
    def valid_proof(transactions, chipsactions, last_hash, proof):
        """Validate a proof of work number and see if it solves the puzzle algorithm (two leading 0s)

        Arguments:
            :transactions: The transactions of the block for which the proof is created.
            :last_hash: The previous block's hash which will be stored in the current block.
            :proof: The proof number we're testing.
        """
        # Create a string with all the hash inputs
        guess = (str([tx.to_ordered_dict() for tx in transactions]) + str([tx.to_ordered_dict() for tx in chipsactions]) + str(last_hash) + str(proof)).encode()
        # Hash the string
        # IMPORTANT: This is NOT the same hash as will be stored in the previous_hash. It's a not a block's hash. It's only used for the proof-of-work algorithm.
        guess_hash = hash_string_256(guess)
        # Only a hash (which is based on the above inputs) which starts with two 0s is treated as valid
        # This condition is of course defined by you. You could also require 10 leading 0s - this would take significantly longer (and this allows you to control the speed at which new blocks can be added)
        return guess_hash[0:2] == '00'
        
    @classmethod
    def verify_chain(cls, blockchain):
        """ Verify the current blockchain and return True if it's valid, False otherwise."""
        for (index, block) in enumerate(blockchain):
            if index == 0:
                continue
            if block.previous_hash != hash_block(blockchain[index - 1]):
                return False
            if not cls.valid_proof(block.transactions[:-1], block.chipsactions, block.previous_hash, block.proof):
                print('Proof of work is invalid')
                return False
        return True

    @staticmethod
    def verify_transaction(transaction, get_balance, check_funds=True):
        """Verify a transaction by checking whether the sender has sufficient coins.

        Arguments:
            :transaction: The transaction that should be verified.
        """
        if check_funds:
            sender_balance = get_balance(transaction.sender)
            return sender_balance >= transaction.amount and Wallet.verify_transaction(transaction)
        else:
            return Wallet.verify_transaction(transaction)
    
    @staticmethod
    def verify_chipsaction(chipsaction, get_balance, check_funds=True):
        """Verify a chipsaction by checking whether the sender has sufficient coins.

        Arguments:
            :chipsaction: The chipsaction that should be verified.
        """
        if check_funds:
            sender_balance = get_balance(chipsaction.sender)
            return sender_balance >= chipsaction.amount and Wallet.verify_chipsaction(chipsaction)
        else:
            return Wallet.verify_chipsaction(chipsaction)

    @classmethod
    def verify_transactions(cls, open_transactions, get_balance):
        """Verifies all open transactions."""
        return all([cls.verify_transaction(tx, get_balance, False) for tx in open_transactions])

    @classmethod
    def verify_chipsactions(cls, open_chipsactions, get_balance):
        """Verifies all open chipsactions."""
        return all([cls.verify_chipsaction(tx, get_balance, False) for tx in open_chipsactions])
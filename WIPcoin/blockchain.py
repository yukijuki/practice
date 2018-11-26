from functools import reduce
import hashlib as hl

import json
import pickle
import requests

from utility.hash_util import hash_block
from utility.verification import Verification
from block import Block
from transaction import Transaction
from chipsaction import Chipsaction
from wallet import Wallet

# The reward we give to miners (for creating a new block)
MINING_REWARD = 10

print(__name__)


class Blockchain:
    """The Blockchain class manages the chain of blocks as well as open transactions and the node on which it's running.

    Attributes:
        :chain: The list of blocks
        :open_transactions: The list of open transactions
        :open_chipsactions: The list of open chipsactions
        :hosting_node: The connected node (which runs the blockchain).
    """

    def __init__(self, public_key, node_id):
        """The constructor of the Blockchain class."""
        # Our starting block for the blockchain
        genesis_block = Block(0, '', [], [], 100, 0)
        # Initializing our (empty) blockchain list
        self.chain = [genesis_block]
        # Unhandled transactions
        self.__open_transactions = []
        self.__open_chipsactions = []
        self.public_key = public_key
        self.__peer_nodes = set()
        self.node_id = node_id
        self.resolve_conflicts = False
        self.load_data()

    # This turns the chain attribute into a property with a getter (the method below) and a setter (@chain.setter)
    @property
    def chain(self):
        return self.__chain[:]

    # The setter for the chain property
    @chain.setter
    def chain(self, val):
        self.__chain = val

    def get_open_transactions(self):
        """Returns a copy of the open transactions list."""
        return self.__open_transactions[:]

    def get_open_chipsactions(self):
        """Returns a copy of the open chipsactions list."""
        return self.__open_chipsactions[:]

    def load_data(self):
        """Initialize blockchain + open transactions + open chipsactions data from a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='r') as f:
                file_content = f.readlines()
                blockchain = json.loads(file_content[0][:-1])
                updated_blockchain = []
                for block in blockchain:
                    converted_tx = [Transaction(
                        tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]
                    converted_chip = [Chipsaction(
                        tx['sender'], tx['recipient'], tx['placeID'], tx['message'], tx['signature'], tx['amount']) for tx in block['chipsactions']]
                    updated_block = Block(
                        block['index'], block['previous_hash'], converted_tx, converted_chip, block['proof'], block['timestamp'])
                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain

                open_transactions = json.loads(file_content[1][:-1])
                # need to convert  the loaded data because Transactions should use OrderedDict
                updated_transactions = []
                for tx in open_transactions:
                    updated_transaction = Transaction(
                        tx['sender'], tx['recipient'], tx['signature'], tx['amount'])
                    updated_transactions.append(updated_transaction)
                self.__open_transactions = updated_transactions

                open_chipsactions = json.loads(file_content[2][:-1])
                # need to convert  the loaded data because Chipsactions should use OrderedDict
                updated_chipsactions = []
                for tx in open_chipsactions:
                    updated_chipsaction = Chipsaction(
                        tx['sender'], tx['recipient'], tx['placeID'], tx['message'], tx['signature'], tx['amount'])
                    updated_chipsactions.append(updated_chipsaction)
                self.__open_chipsactions = updated_chipsactions

                peer_nodes = json.loads(file_content[3])
                self.__peer_nodes = set(peer_nodes)
        except (IOError, IndexError):
            pass
        finally:
            print('Cleanup!')

    def save_data(self):
        """Save blockchain + open transactions and open chipsactions snapshot to a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='w') as f:
                saveable_chain = [block.__dict__ for block in [Block(block_el.index, block_el.previous_hash, 
                [tx.__dict__ for tx in block_el.transactions], 
                [tx.__dict__ for tx in block_el.chipsactions],
                    block_el.proof, block_el.timestamp) for block_el in self.__chain]]
                f.write(json.dumps(saveable_chain))
                f.write('\n')
                saveable_tx = [tx.__dict__ for tx in self.__open_transactions]
                f.write(json.dumps(saveable_tx))
                f.write('\n')
                saveable_chip = [tx.__dict__ for tx in self.__open_chipsactions]
                f.write(json.dumps(saveable_chip))
                f.write('\n')
                f.write(json.dumps(list(self.__peer_nodes)))
        except IOError:
            print('Saving failed!')

    def proof_of_work(self):
        """Generate a proof of work for the open transactions, the hash of the previous block and a random number (which is guessed until it fits)."""
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        proof = 0
        # Try different PoW numbers and return the first valid one
        while not Verification.valid_proof(self.__open_transactions, self.__open_chipsactions, last_hash, proof):
            proof += 1
        return proof

    def get_balance(self, sender=None):
        """Calculate and return the balance for a participant.
        """
        if sender == None:
            if self.public_key == None:
                return None
            participant = self.public_key
        else:
            participant = sender

        # Fetch a list of tx and chip transactions sent (empty lists are returned if the person was NOT the sender)
        # This fetches sent amounts of transactions that were already included in blocks of the blockchain
        tx_sender = [[tx.amount for tx in block.transactions
                      if tx.sender == participant] for block in self.__chain]
        open_tx_sender = [tx.amount
                          for tx in self.__open_transactions if tx.sender == participant]
        tx_sender.append(open_tx_sender)
        print(tx_sender)
        amount_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                             if len(tx_amt) > 0 else tx_sum + 0, tx_sender, 0)

        tx_sender1 = [[tx.amount for tx in block.chipsactions
                      if tx.sender == participant] for block in self.__chain]
        open_tx_sender1 = [tx.amount
                          for tx in self.__open_chipsactions if tx.sender == participant]
        tx_sender1.append(open_tx_sender1)
        print(tx_sender1)
        amount_sent1 = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                             if len(tx_amt) > 0 else tx_sum + 0, tx_sender1, 0)


        # This fetches received tx and chip amounts of transactions that were already included in blocks of the blockchain
        tx_recipient = [[tx.amount for tx in block.transactions
                         if tx.recipient == participant] for block in self.__chain]
        amount_received = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                                 if len(tx_amt) > 0 else tx_sum + 0, tx_recipient, 0)

        tx_recipient1 = [[tx.amount for tx in block.chipsactions
                         if tx.recipient == participant] for block in self.__chain]
        amount_received1 = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                                 if len(tx_amt) > 0 else tx_sum + 0, tx_recipient1, 0)
                                 
        # Return the total balance
        total_amount_sent = amount_sent + amount_sent1
        total_amount_received = amount_received + amount_received1
        return total_amount_received - total_amount_sent

    def get_last_blockchain_value(self):
        """ Returns the last value of the current blockchain. """
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]


    def add_transaction(self, sender, recipient, signature, amount=1.0, is_receiving=False):
        """ 
        Arguments:
            :sender: The sender of the coins.
            :recipient: The recipient of the coins.
            :amount: The amount of coins sent with the transaction (default = 1.0)
        """
        transaction = Transaction(sender, recipient, signature, amount)
        if Verification.verify_transaction(transaction, self.get_balance):
            self.__open_transactions.append(transaction)
            self.save_data()
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-transaction'.format(node)
                    try:
                        response = requests.post(url, json={
                                                 'sender': sender, 'recipient': recipient, 'amount': amount, 'signature': signature})
                        if response.status_code == 400 or response.status_code == 500:
                            print('Transaction declined, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False

    def add_chipsaction(self, sender, recipient, placeID, message, signature, amount=1.0, is_receiving=False):
        """ 
        Arguments:
            :sender: The sender of the coins.
            :recipient: The address of the author.
            :placeID: The UUID of the Beacon.
            :message: The message from the supporter.
            :amount: The amount of coins sent with the chipsaction
        """
        chipsaction = Chipsaction(sender, recipient, placeID, message, signature, amount)
        if Verification.verify_chipsaction(chipsaction, self.get_balance):
            self.__open_chipsactions.append(chipsaction)
            self.save_data()
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-chipsaction'.format(node)
                    try:
                        response = requests.post(url, json={
                                                 'sender': sender, 'recipient': recipient, 'placeID': placeID, 'message': message, 'amount': amount, 'signature': signature})
                        if response.status_code == 400 or response.status_code == 500:
                            print('Chipsaction declined, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False

    def mine_block(self):
        """Create a new block and add open transactions and chipsactions to it."""
        if self.public_key == None:
            return None
        last_block = self.__chain[-1]
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()
        reward_transaction = Transaction(
            'MINING', self.public_key, '', MINING_REWARD)

        copied_transactions = self.__open_transactions[:]
        for tx in copied_transactions:
            if not Wallet.verify_transaction(tx):
                return None
        copied_transactions.append(reward_transaction)

        copied_chipsactions = self.__open_chipsactions[:]
        for tx in copied_chipsactions:
            if not Wallet.verify_chipsaction(tx):
                return None

        block = Block(len(self.__chain), hashed_block,
                      copied_transactions, copied_chipsactions, proof)
        self.__chain.append(block)
        self.__open_transactions = []
        self.__open_chipsactions = []
        self.save_data()
        for node in self.__peer_nodes:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['transactions'] = [
                tx.__dict__ for tx in converted_block['transactions']]
            converted_block['chipsactions'] = [
                tx.__dict__ for tx in converted_block['chipsactions']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or response.status_code == 500:
                    print('Block declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return block

    def add_block(self, block):
        """Add a block which was received via broadcasting to the local blockchain."""
        # Create a list of transaction objects
        transactions = [Transaction(
            tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]    
        chipsactions = [Chipsaction(
            tx['sender'], tx['recipient'], tx['placeID'], tx['message'], tx['signature'], tx['amount']) for tx in block['chipsactions']]    
        # Validate the proof of work of the block and store the result (True or False) in a variable
        proof_is_valid = Verification.valid_proof(
            transactions[:-1], chipsactions, block['previous_hash'], block['proof'])
        # Check if previous_hash stored in the block is equal to the local blockchain's last block's hash and store the result in a block
        hashes_match = hash_block(self.chain[-1]) == block['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        # Create a Block object
        converted_block = Block(
            block['index'], block['previous_hash'], transactions, chipsactions, block['proof'], block['timestamp'])
        self.__chain.append(converted_block)
        stored_transactions = self.__open_transactions[:]
        stored_chipsactions = self.__open_chipsactions[:]
        # Check which open transactions were included in the received block and remove them
        # This could be improved by giving each transaction an ID that would uniquely identify it
        for itx in block['transactions']:
            for opentx in stored_transactions:
                if opentx.sender == itx['sender'] and opentx.recipient == itx['recipient'] and opentx.amount == itx['amount'] and opentx.signature == itx['signature']:
                    try:
                        self.__open_transactions.remove(opentx)
                    except ValueError:
                        print('Item was already removed')

        for itx in block['chipsactions']:
            for opentx in stored_chipsactions:
                if opentx.sender == itx['sender'] and opentx.recipient == itx['recipient'] and opentx.sender == itx['placeID'] and opentx.recipient == itx['message'] and opentx.amount == itx['amount'] and opentx.signature == itx['signature']:
                    try:
                        self.__open_chipsactions.remove(opentx)
                    except ValueError:
                        print('Item was already removed')
        self.save_data()
        return True

    def resolve(self):
        """Checks all peer nodes' blockchains and replaces the local one with longer valid ones."""
        # Initialize the winner chain with the local chain
        winner_chain = self.chain
        replace = False
        for node in self.__peer_nodes:
            url = 'http://{}/chain'.format(node)
            try:
                # Send a request and store the response
                response = requests.get(url)
                # Retrieve the JSON data as a dictionary
                node_chain = response.json()
                # Convert the dictionary list to a list of block AND transaction objects
                node_chain = [Block(block['index'], block['previous_hash'], [Transaction(
                    tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']],
                    [Chipsaction(tx['sender'], tx['recipient'], tx['placeID'], tx['message'], tx['signature'], tx['amount']) for tx in block['chipsactions']],
                                    block['proof'], block['timestamp']) for block in node_chain]
                node_chain_length = len(node_chain)
                local_chain_length = len(winner_chain)
                # Store the received chain as the current winner chain if it's longer AND valid
                if node_chain_length > local_chain_length and Verification.verify_chain(node_chain):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        # Replace the local chain with the winner chain
        self.chain = winner_chain
        if replace:
            self.__open_transactions = []
            self.__open_chipsactions = []
        self.save_data()
        return replace

    def add_peer_node(self, node):
        """Adds a new node to the peer node set.

        Arguments:
            :node: The node URL which should be added.
        """
        self.__peer_nodes.add(node)
        self.save_data()

    def remove_peer_node(self, node):
        """Removes a node from the peer node set.

        Arguments:
            :node: The node URL which should be removed.
        """
        self.__peer_nodes.discard(node)
        self.save_data()

    def get_peer_nodes(self):
        """Return a list of all connected peer nodes."""
        return list(self.__peer_nodes)
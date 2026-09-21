"""Server-owned peer/account binding; not yet wired into engine network callbacks."""


class PlayerSessions:
    def __init__(self, store, max_players=128):
        if type(max_players) is not int or not 1 <= max_players <= 128:
            raise ValueError('Player limit must be 1..128')
        self.store = store
        self.max_players = max_players
        self.peers = {}
        self.accounts = {}

    def login(self, peer_id, login, password):
        # peer_id must come from the server transport, never from a client payload.
        if type(peer_id) is not int or not 1 <= peer_id <= 2**32 - 1:
            raise ValueError('Invalid transport peer')
        account_id = self.store.authenticate(login, password)
        if account_id is None:
            raise ValueError('Authentication failed')
        existing = self.peers.get(peer_id)
        if existing is not None and existing != account_id:
            raise ValueError('Peer already bound to an account')
        if account_id in self.accounts and self.accounts[account_id] != peer_id:
            raise ValueError('Account already connected')
        if existing is None and len(self.peers) >= self.max_players:
            raise ValueError('Server full')
        self.peers[peer_id] = account_id
        self.accounts[account_id] = peer_id
        return account_id

    def account(self, peer_id):
        account_id = self.peers.get(peer_id)
        if account_id is None:
            raise ValueError('Unauthenticated peer')
        return account_id

    def is_admin(self, peer_id):
        account_id = self.peers.get(peer_id)
        return account_id is not None and self.store.role(account_id) == 'admin'

    def load_player(self, peer_id):
        return self.store.load_player(self.account(peer_id))

    def checkpoint(self, peer_id, server_state, expected_revision):
        return self.store.save_player(self.account(peer_id), server_state, expected_revision)

    def disconnect(self, peer_id, server_state, expected_revision):
        account_id = self.account(peer_id)
        revision = self.store.save_player(account_id, server_state, expected_revision)
        # Retain the binding on storage failure so callers can retry without losing state.
        del self.peers[peer_id]
        del self.accounts[account_id]
        return revision

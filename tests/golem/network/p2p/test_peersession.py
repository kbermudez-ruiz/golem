import mock
from mock import MagicMock, Mock
import random
import unittest

from golem import testutils
from golem.core.keysauth import EllipticalKeysAuth, KeysAuth
from golem.core.variables import APP_VERSION, P2P_PROTOCOL_ID
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import (PeerSession, logger, PeerSessionInfo)
from golem.network.transport.message import MessageHello, MessageStopGossip
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth


class TestPeerSession(TestWithKeysAuth, LogTestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/network/p2p/peersession.py',]

    def setUp(self):
        super(TestPeerSession, self).setUp()
        random.seed()
        self.peer_session = PeerSession(MagicMock())

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_hello(self, send_mock):
        self.maxDiff = None
        self.peer_session.conn.server.node = node = 'node info'
        self.peer_session.conn.server.node_name = node_name = 'node name'
        self.peer_session.conn.server.keys_auth.get_key_id.return_value = \
            key_id = 'client_key_id'
        self.peer_session.conn.server.metadata_manager.\
            get_metadata.return_value = metadata = 'metadata'
        self.peer_session.conn.server.cur_port = port = random.randint(1, 50000)
        self.peer_session.hello()
        send_mock.assert_called_once_with(mock.ANY, mock.ANY)

        expected = [
            ['rand_val', self.peer_session.rand_val],
            ['proto_id', P2P_PROTOCOL_ID],
            ['node_name', node_name],
            ['node_info', node],
            ['port', port],
            ['client_ver', APP_VERSION],
            ['client_key_id', key_id],
            ['solve_challenge', False],
            ['challenge', None],
            ['difficulty', 0],
            ['metadata', metadata],
        ]

        self.assertEqual(send_mock.call_args[0][1].slots(), expected)

    def test_encrypt_decrypt(self):
        ps = PeerSession(MagicMock())
        ps2 = PeerSession(MagicMock())

        ek = EllipticalKeysAuth(self.path, "RANDOMPRIV", "RANDOMPUB")
        ek2 = EllipticalKeysAuth(self.path, "RANDOMPRIV2", "RANDOMPUB2")
        ps.p2p_service.encrypt = ek.encrypt
        ps.p2p_service.decrypt = ek.decrypt
        ps.key_id = ek2.key_id
        ps2.p2p_service.encrypt = ek2.encrypt
        ps2.p2p_service.decrypt = ek2.decrypt
        ps2.key_id = ek.key_id

        data = b"abcdefghijklm" * 1000
        self.assertEqual(ps2.decrypt(ps.encrypt(data)), data)
        self.assertEqual(ps.decrypt(ps2.encrypt(data)), data)
        with self.assertLogs(logger, level='INFO') as l:
            self.assertEqual(ps2.decrypt(data), data)
        self.assertTrue(any("not encrypted" in log for log in l.output))

    def test_react_to_hello(self):

        conn = MagicMock()
        conf = MagicMock()
        conf.opt_peer_num = 10

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        peer_session = PeerSession(conn)
        peer_session.p2p_service = P2PService(node, conf, keys_auth, False)
        peer_session.p2p_service.metadata_manager = MagicMock()
        peer_session.send = MagicMock()
        peer_session.disconnect = MagicMock()
        peer_session._solve_challenge = MagicMock()

        def create_verify(value):
            def verify(*args):
                return value
            return verify

        key_id = 'deadbeef'
        peer_info = MagicMock()
        peer_info.key = key_id
        msg = MessageHello(port=1, node_name='node2', client_key_id=key_id,
                           node_info=peer_info, proto_id=-1)

        peer_session.verify = create_verify(False)
        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(PeerSession.DCRUnverified)

        peer_session.verify = create_verify(True)
        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(
            PeerSession.DCRProtocolVersion)

        msg.proto_id = P2P_PROTOCOL_ID

        peer_session._react_to_hello(msg)
        assert key_id in peer_session.p2p_service.peers
        assert peer_session.p2p_service.peers[key_id]

        peer_session.p2p_service.peers[key_id] = MagicMock()
        conn.opened = True
        peer_session.key_id = None

        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(
            PeerSession.DCRDuplicatePeers)

    def test_disconnect(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = MagicMock()
        peer_session.dropped = MagicMock()
        peer_session.send = MagicMock()
        peer_session.conn = Mock()

        peer_session.conn.opened = False
        peer_session.disconnect(PeerSession.DCRProtocolVersion)
        assert not peer_session.dropped.called
        assert not peer_session.send.called

        peer_session.conn.opened = True
        peer_session.disconnect(PeerSession.DCRProtocolVersion)
        assert peer_session.dropped.called
        assert peer_session.send.called

        peer_session.send.called = False
        peer_session.disconnect(PeerSession.DCRProtocolVersion)
        assert not peer_session.send.called

    def test_dropped(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = MagicMock()

        peer_session.dropped()
        assert peer_session.p2p_service.remove_peer.called
        assert not peer_session.p2p_service.remove_pending_conn.called

    def test_react_to_stop_gossip(self):
        conn = MagicMock()
        conf = MagicMock()
        conf.opt_peer_num = 10

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        peer_session = PeerSession(conn)
        peer_session.p2p_service = P2PService(node, conf, keys_auth, False)
        peer_session.key_id = "NEW KEY_ID"
        peer_session._react_to_stop_gossip(MessageStopGossip())

    def test_verify(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        keys_auth = EllipticalKeysAuth(self.path)
        peer_session.key_id = keys_auth.get_key_id()
        peer_session.p2p_service.verify_sig = keys_auth.verify
        msg = MessageStopGossip()
        assert not peer_session.verify(msg)
        msg.sig = keys_auth.sign(msg.get_short_hash())
        assert peer_session.verify(msg)

    def test_interpret(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.key_id = "KEY_ID"
        msg = MessageStopGossip()
        peer_session.interpret(msg)
        assert peer_session.p2p_service.set_last_message.called


class TestPeerSessionInfo(unittest.TestCase):

    def test(self):

        session = PeerSession(MagicMock())

        session.unknown_property = False
        session_info = PeerSessionInfo(session)

        simple_attributes = [
            'address', 'port',
            'verified', 'degree',
            'key_id', 'node_name',
            'listen_port', 'conn_id'
        ]
        attributes = simple_attributes + ['node_info']

        for attr in attributes:
            assert hasattr(session_info, attr)
        assert not hasattr(session_info, 'unknown_property')

        simplified = session_info.get_simplified_repr()
        for attr in simple_attributes:
            simplified[attr]
        with self.assertRaises(KeyError):
            simplified["node_id"]

import base64
from pathlib import Path
import tempfile
import time
import unittest
import libtorrent as lt
from server import Engine

SETTINGS = {'listen_interfaces': '127.0.0.1:0', 'enable_dht': False, 'enable_lsd': False,
            'enable_upnp': False, 'enable_natpmp': False, 'allow_multiple_connections_per_ip': True}

def wait_for(predicate, timeout=20):
    until = time.time() + timeout
    while time.time() < until:
        if predicate(): return
        time.sleep(.1)
    raise AssertionError('Timed out waiting for local torrent transfer')

class EngineTests(unittest.TestCase):
    def test_transfers_restore_and_controls(self):
        for version, flags in [('v1', lt.create_torrent.v1_only), ('v2', lt.create_torrent.v2_only), ('hybrid', 0), ('magnet', 0)]:
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                seed = root / 'seed'; seed.mkdir()
                payload = (b'MeowTOrrent local integration test\n' * 8192)
                (seed / 'sample.txt').write_bytes(payload)
                storage = lt.file_storage(); lt.add_files(storage, str(seed / 'sample.txt'))
                torrent = lt.create_torrent(storage, 16384, flags)
                lt.set_piece_hashes(torrent, str(seed))
                encoded = lt.bencode(torrent.generate())
                source = base64.b64encode(encoded).decode()
                seeder = lt.session(SETTINGS)
                params = lt.add_torrent_params(); params.ti = lt.torrent_info(lt.bdecode(encoded)); params.save_path = str(seed)
                params.flags &= ~lt.torrent_flags.paused; params.flags &= ~lt.torrent_flags.auto_managed
                sh = seeder.add_torrent(params)
                wait_for(lambda: sh.status().is_seeding)
                engine = Engine(root / 'state', root / 'downloads', SETTINGS)
                key = engine.add(lt.make_magnet_uri(params.ti), 'magnet') if version == 'magnet' else engine.add(source, 'file')
                engine.handles[key].connect_peer(('127.0.0.1', seeder.listen_port()))
                wait_for(lambda: engine.info()[0]['progress'] == 1)
                self.assertEqual((root / 'downloads' / 'sample.txt').read_bytes(), payload)
                engine.action(key, 'stop')
                self.assertEqual(engine.info()[0]['state'], 'paused')
                restored = Engine(root / 'state', root / 'downloads', SETTINGS)
                self.assertEqual(restored.info()[0]['state'], 'paused')
                restored.action(key, 'start')
                self.assertFalse(restored.records[key]['paused'])
                restored.action(key, 'delete')
                self.assertEqual(restored.info(), [])
                self.assertTrue((root / 'downloads' / 'sample.txt').exists())
                engine.session.pause(); seeder.pause()

    def test_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Path(folder)/'state', Path(folder)/'downloads', SETTINGS)
            with self.assertRaises(Exception): engine.add('bad magnet', 'magnet')
            with self.assertRaises(Exception): engine.add('not base64', 'file')
            self.assertEqual(engine.info(), [])

if __name__ == '__main__': unittest.main()

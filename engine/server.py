"""MeowTOrrent's local BitTorrent engine. No external client or account required."""
import base64
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import libtorrent as lt

class Engine:
    def __init__(self, root, downloads, settings=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.downloads = Path(downloads).resolve()
        self.downloads.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.session = lt.session(settings or {'listen_interfaces': '0.0.0.0:6881,[::]:6881'})
        self.records = {}
        self.handles = {}
        self.index = self.root / 'library.json'
        if self.index.exists():
            for record in json.loads(self.index.read_text()):
                self.add(record['source'], record['kind'], record.get('paused', False))

    def persist(self):
        tmp = self.index.with_suffix('.tmp')
        tmp.write_text(json.dumps(list(self.records.values())))
        tmp.replace(self.index)

    def add(self, source, kind, paused=False):
        with self.lock:
            if kind == 'magnet':
                params = lt.parse_magnet_uri(source)
            elif kind == 'file':
                params = lt.add_torrent_params()
                params.ti = lt.torrent_info(lt.bdecode(base64.b64decode(source, validate=True)))
            else:
                raise ValueError('Choose a magnet link or .torrent file')
            params.save_path = str(self.downloads)
            params.flags &= ~lt.torrent_flags.auto_managed
            if paused:
                params.flags |= lt.torrent_flags.paused
            else:
                params.flags &= ~lt.torrent_flags.paused
            handle = self.session.add_torrent(params)
            hashes = handle.info_hashes()
            key = str(hashes.v1) if hashes.has_v1() else str(hashes.v2)
            if key in self.handles:
                return key
            self.handles[key] = handle
            self.records[key] = {'source': source, 'kind': kind, 'paused': paused}
            self.persist()
            return key

    def info(self):
        with self.lock:
            rows = []
            for key, handle in self.handles.items():
                s = handle.status()
                state = ('paused' if self.records[key]['paused'] else 'error' if s.errc.value() else
                         'uploading' if s.is_seeding else 'metadata' if not s.has_metadata else
                         'checking' if s.state in (lt.torrent_status.checking_files, lt.torrent_status.checking_resume_data) else 'downloading')
                remaining = max(0, s.total_wanted - s.total_wanted_done)
                rows.append(dict(hash=key, name=s.name or 'Fetching torrent metadata…', size=s.total_wanted,
                    progress=s.progress, dlspeed=s.download_payload_rate, upspeed=s.upload_payload_rate,
                    state=state, num_seeds=s.num_seeds, eta=remaining / s.download_payload_rate if s.download_payload_rate else 8640000,
                    save_path=str(self.downloads), error=s.errc.message() if s.errc.value() else ''))
            return rows

    def action(self, key, action):
        with self.lock:
            if key not in self.handles:
                raise ValueError('Torrent no longer exists')
            handle = self.handles[key]
            if action == 'delete':
                self.session.remove_torrent(handle)  # Retain downloaded files.
                del self.handles[key]
                del self.records[key]
            elif action in ('start', 'stop'):
                self.records[key]['paused'] = action == 'stop'
                handle.pause() if action == 'stop' else handle.resume()
            else:
                raise ValueError('Unknown torrent action')
            self.persist()


def serve():
    origin = os.environ.get('MEOW_ORIGIN', 'http://localhost:5173').rstrip('/')
    token = secrets.token_urlsafe(32)
    port = int(os.environ.get('MEOW_PORT', '8788'))
    engine = Engine(os.environ.get('MEOW_STATE', str(Path.home() / '.meowtorrent')),
                    os.environ.get('MEOW_DOWNLOADS', str(Path.home() / 'Downloads' / 'MeowTOrrent')))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            if self.headers.get('Origin') == origin:
                self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def allowed(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}') and self.headers.get('Origin') == origin
        def do_OPTIONS(self):
            if not self.allowed(): return self.reply(403, 'Origin not allowed')
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()
        def do_GET(self):
            if not self.allowed(): return self.reply(403, 'Origin not allowed')
            if self.path == '/api/session':
                return self.reply(200, dict(token=token, downloads=str(engine.downloads), version=lt.version))
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                return self.reply(401, 'Invalid local engine token')
            if self.path == '/api/torrents': return self.reply(200, engine.info())
            self.reply(404, 'Not found')
        def do_POST(self):
            if not self.allowed(): return self.reply(403, 'Origin not allowed')
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                return self.reply(401, 'Invalid local engine token')
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 14 * 1024 * 1024: return self.reply(413, 'Torrent file must be under 10 MB')
                data = json.loads(self.rfile.read(length))
                if self.path == '/api/torrents/add':
                    key = engine.add(data['source'], data['kind'])
                    return self.reply(200, {'hash': key})
                if self.path in ('/api/torrents/start', '/api/torrents/stop', '/api/torrents/delete'):
                    engine.action(data['hash'], self.path.rsplit('/', 1)[1])
                    return self.reply(200, {'ok': True})
                self.reply(404, 'Not found')
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                self.reply(400, str(exc))
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'MeowTOrrent engine ready at http://127.0.0.1:{port}\nDownloads: {engine.downloads}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': serve()

"""Supabase giả lập tối thiểu cho test e2e (KHÔNG dùng production):
- Storage: GET/POST /storage/v1/object/<bucket>/<key>, POST /storage/v1/object/list/<bucket>, POST /storage/v1/object/move
- PostgREST: POST /rest/v1/<table>?on_conflict=a,b  (Prefer: resolution=merge-duplicates) → INSERT .. ON CONFLICT DO UPDATE
Chạy: python tests/mock_supabase.py --port 54321 --storage /tmp/store --dsn "host=... port=... user=postgres"
"""
import argparse, json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb
from psycopg import sql

KEY = 'service-test-key'


def make_handler(store: Path, dsn: str):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _auth(self):
            if self.headers.get('apikey') != KEY:
                self._send(401, {'message': 'bad key'}); return False
            return True

        def _send(self, code, body=b'', ctype='application/json'):
            if not isinstance(body, (bytes, bytearray)): body = json.dumps(body).encode()
            self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def _body(self):
            n = int(self.headers.get('Content-Length', 0)); return self.rfile.read(n)

        def do_GET(self):
            if not self._auth(): return
            p = urlparse(self.path).path
            if p.startswith('/storage/v1/object/'):
                rest = p[len('/storage/v1/object/'):]
                f = store / rest
                if f.is_file(): return self._send(200, f.read_bytes(), 'application/octet-stream')
                return self._send(400, {'statusCode': '404', 'error': 'not_found', 'message': 'Object not found'})
            self._send(404, {'message': 'not found'})

        def do_POST(self):
            if not self._auth(): return
            u = urlparse(self.path); p = u.path
            if p.startswith('/storage/v1/object/list/'):
                bucket = p.split('/')[-1]; prefix = json.loads(self._body())['prefix']
                d = store / bucket / prefix
                items = [{'name': x.name, 'id': x.name} for x in sorted(d.iterdir()) if x.is_file()] if d.exists() else []
                return self._send(200, items)
            if p == '/storage/v1/object/move':
                b = json.loads(self._body()); src = store / b['bucketId'] / b['sourceKey']; dst = store / b['bucketId'] / b['destinationKey']
                dst.parent.mkdir(parents=True, exist_ok=True); src.rename(dst); return self._send(200, {'message': 'ok'})
            if p.startswith('/storage/v1/object/'):
                f = store / p[len('/storage/v1/object/'):]
                f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(self._body()); return self._send(200, {'Key': str(f)})
            if p.startswith('/rest/v1/'):
                table = p.split('/')[-1]; conflict = parse_qs(u.query)['on_conflict'][0].split(',')
                rows = json.loads(self._body())
                if isinstance(rows, dict): rows = [rows]
                if not rows: return self._send(201, b'')
                cols = list(rows[0].keys())
                if any(list(r.keys()) != cols for r in rows):
                    return self._send(400, {'message': 'All object keys must match'})
                q = sql.SQL('insert into public.{} ({}) values ({}) on conflict ({}) do update set {}').format(
                    sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, cols)),
                    sql.SQL(',').join(sql.Placeholder() * len(cols)), sql.SQL(',').join(map(sql.Identifier, conflict)),
                    sql.SQL(',').join(sql.SQL('{0}=excluded.{0}').format(sql.Identifier(c)) for c in cols if c not in conflict)
                    or sql.SQL('{0}=excluded.{0}').format(sql.Identifier(conflict[0])))
                try:
                    with psycopg.connect(dsn, autocommit=False) as cn, cn.cursor() as cur:
                        cur.executemany(q, [[Jsonb(r[c]) if isinstance(r[c], (dict, list)) else r[c] for c in cols] for r in rows])
                        cn.commit()
                except Exception as e:
                    return self._send(400, {'message': str(e)})
                return self._send(201, b'')
            self._send(404, {'message': 'not found'})
    return H


def serve(port, store, dsn, background=False):
    srv = ThreadingHTTPServer(('127.0.0.1', port), make_handler(Path(store), dsn))
    if background:
        threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv
    srv.serve_forever()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--port', type=int, default=54321)
    ap.add_argument('--storage', required=True); ap.add_argument('--dsn', required=True)
    a = ap.parse_args(); serve(a.port, a.storage, a.dsn)

#!/usr/bin/env python3
"""Serve the site for review with Cache-Control: no-store on every response, so a reload always shows the working tree.

    python3 tools/serve.py               # the site directory on 0.0.0.0:8000
    python3 tools/serve.py --port 8001   # another port
"""
import argparse, functools, http.server, os

SITE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


class NoStore(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='0.0.0.0'); ap.add_argument('--port', type=int, default=8000)
    a = ap.parse_args()
    handler = functools.partial(NoStore, directory=SITE)
    with http.server.ThreadingHTTPServer((a.host, a.port), handler) as srv:
        print(f'serving {SITE} on http://{a.host}:{a.port}/ with Cache-Control: no-store', flush=True)
        srv.serve_forever()


if __name__ == '__main__':
    main()

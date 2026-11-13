"""Serve root index.html and reports/ on loopback; keep raw files private."""
import argparse
import json
import getpass
import os
import threading
from urllib.error import HTTPError
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote

class ReportHandler(SimpleHTTPRequestHandler):
    def serve_index(self, body=True):
        raw=(Path(__file__).resolve().parents[1]/'index.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        if body:self.wfile.write(raw)
    def do_HEAD(self):
        if urlsplit(self.path).path in ('/','/index.html'):
            self.serve_index(body=False);return
        super().do_HEAD()
    def do_GET(self):
        path=unquote(urlsplit(self.path).path)
        if path in ('/','/index.html'):
            self.serve_index();return
        if path in ('/route_map_naver.html','/reports/route_map_naver.html'):
            self.send_response(302);self.send_header('Location','/');self.end_headers();return
        if path.startswith('/reports/'):
            self.path=path[len('/reports'):]
        if self.path=='/api/config':
            service=self.server.route_service
            raw=json.dumps({'client_id':service.client_id if service else None}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if any(part.startswith('.') for part in self.path.split('?')[0].split('/')):
            self.send_error(404);return
        super().do_GET()
    def do_POST(self):
        if self.path not in ('/api/compare','/api/search'):
            self.send_error(404);return
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://localhost:{self.server.server_port}',f'http://127.0.0.1:{self.server.server_port}'):
            self.send_error(403);return
        code=200
        try:
            if not self.server.route_service:raise ValueError('길찾기 서버가 비활성입니다. --naver 옵션으로 서버를 실행하세요.')
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=4096:raise ValueError('잘못된 요청 크기입니다.')
            body=json.loads(self.rfile.read(size))
            if not self.server.route_lock.acquire(blocking=False):raise ValueError('경로 계산 중입니다. 잠시 후 다시 시도하세요.')
            try:result=(self.server.route_service.search(body) if self.path=='/api/search' else self.server.route_service.compare(body))
            finally:self.server.route_lock.release()
        except HTTPError as error:
            code=502;result={'error':f'네이버 API HTTP {error.code}: Directions 5/Geocoding 선택 및 서버 인증키를 확인하세요.'}
        except ValueError as error:
            code=400;result={'error':str(error)}
        except Exception:
            code=502;result={'error':'길찾기 요청에 실패했습니다. 네트워크와 서버 설정을 확인하세요.'}
        raw=json.dumps(result,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()
    def log_message(self, format, *args):
        pass  # No query strings or credentials in server logs.

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--naver',action='store_true',help='Enable Directions 5; prompt credentials locally')
    args=parser.parse_args()
    service=None
    if args.naver:
        from naver_route_service import RouteService
        client_id=os.environ.get('NAVER_MAPS_CLIENT_ID') or input('Maps Client ID: ').strip()
        secret=os.environ.get('NAVER_MAPS_CLIENT_SECRET') or getpass.getpass('Maps Client Secret (화면에 표시되지 않음): ')
        if not client_id or not secret:raise SystemExit('인증키가 필요합니다.')
        service=RouteService(client_id,secret)
    root=Path(__file__).resolve().parents[1]/'reports'
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(ReportHandler,directory=str(root)))
    server.route_service=service
    server.route_lock=threading.Lock()
    print(f'네이버 지도: http://localhost:{args.port}/',flush=True)
    print('위 주소를 브라우저에서 열면 지도가 자동 연결됩니다. 종료: Ctrl+C',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

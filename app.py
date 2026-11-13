"""WSGI entrypoint for Vercel; reuse the local routing service."""
import math
import os
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from scripts.naver_route_service import RouteService

ROOT=Path(__file__).resolve().parent
app=Flask(__name__,static_folder=None)
app.config['MAX_CONTENT_LENGTH']=4096
app.json.ensure_ascii=False

@lru_cache(maxsize=1)
def service_for(client_id,secret):
    return RouteService(client_id,secret)

def get_service():
    client_id=os.environ.get('NAVER_MAPS_CLIENT_ID','').strip()
    secret=os.environ.get('NAVER_MAPS_CLIENT_SECRET','').strip()
    if not client_id or not secret:
        raise ValueError('Vercel Settings → Environment Variables에 NAVER_MAPS_CLIENT_ID와 NAVER_MAPS_CLIENT_SECRET을 설정한 뒤 Redeploy하세요.')
    return service_for(client_id,secret)

@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    return response

@app.get('/')
@app.get('/index.html')
def index():
    return send_file(ROOT/'index.html',mimetype='text/html')

@app.get('/favicon.ico')
def favicon():
    return '',204

@app.get('/api/config')
def config():
    client_id=os.environ.get('NAVER_MAPS_CLIENT_ID','').strip()
    if not client_id:
        return jsonify(error='Vercel 환경변수 NAVER_MAPS_CLIENT_ID를 설정하고 Redeploy하세요.'),503
    # Web SDK Client ID is public. Secret must never leave the server.
    return jsonify(client_id=client_id)

@app.get('/api/health')
def health():
    return jsonify(ok=True,configured=bool(os.environ.get('NAVER_MAPS_CLIENT_ID') and os.environ.get('NAVER_MAPS_CLIENT_SECRET')))

def process(kind):
    origin=request.headers.get('Origin')
    if origin:
        parsed=urlsplit(origin)
        if parsed.scheme not in ('http','https') or parsed.netloc!=request.host:
            return jsonify(error='현재 사이트에서만 요청할 수 있습니다.'),403
    try:
        body=request.get_json(silent=True)
        if not isinstance(body,dict):raise ValueError('JSON 객체로 요청하세요.')
        if kind=='compare':
            for key in ('start','goal'):
                point=body.get(key)
                if not isinstance(point,list) or len(point)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point):
                    raise ValueError('유효한 출발·도착 좌표를 선택하세요.')
            hour=body.get('hour',17);delay=body.get('delay',.1)
            if type(hour) is not int or hour not in (0,6,11,14,17,21):raise ValueError('지원하는 상권 시간대를 선택하세요.')
            if type(delay) not in (int,float) or not math.isfinite(delay) or not 0<=delay<=.5:raise ValueError('허용 지연은 0~50% 범위입니다.')
            body['hour']=hour;body['delay']=delay
        service=get_service()
        result=service.search(body) if kind=='search' else service.compare(body)
        return jsonify(result)
    except (BadRequest,RequestEntityTooLarge):
        return jsonify(error='요청 JSON과 크기를 확인하세요.'),400
    except ValueError as error:
        return jsonify(error=str(error)),400
    except HTTPError as error:
        return jsonify(error=f'네이버 API HTTP {error.code}: 같은 Application의 Directions 5·Geocoding 선택과 서버 인증키를 확인하세요.'),502
    except (URLError,TimeoutError):
        return jsonify(error='네이버 API 응답이 지연되거나 연결되지 않았습니다. 잠시 후 다시 검색하세요.'),504
    except Exception:
        # Do not return upstream URLs, credentials or stack traces.
        return jsonify(error='경로 검색 서버 오류입니다. Vercel Runtime Logs와 환경변수 설정을 확인하세요.'),500

@app.post('/api/search')
def search():
    return process('search')

@app.post('/api/compare')
def compare():
    return process('compare')

@app.errorhandler(RequestEntityTooLarge)
def too_large(error):
    return jsonify(error='요청 크기가 너무 큽니다.'),413

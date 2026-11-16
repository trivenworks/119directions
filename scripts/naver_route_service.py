"""Bounded NAVER candidate search and commercial-area exposure scoring."""
import json, math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def recommend_route(fastest,avoid,delay):
    """Analysis policy, not an operational emergency-vehicle recommendation."""
    bound=fastest['duration_s']*(1+delay)
    reduction=fastest['busy_distance_m']-avoid['busy_distance_m']
    eligible=avoid['duration_s']<=bound+1e-6 and reduction>=1.0
    chosen=avoid if eligible else fastest
    reduction=max(0.,fastest['busy_distance_m']-chosen['busy_distance_m'])
    return {
        'kind':'congestion_avoidance' if eligible else 'time',
        'reason_code':'less_busy_within_delay' if eligible else 'prefer_fastest_no_reduction',
        'reason':'설정한 허용 지연 안에서 혼잡 상권 통과 거리를 줄이는 대안입니다.' if eligible else '허용 지연 안에서 혼잡 통과 거리를 1m 이상 줄이는 대안이 없어 최단시간 경로를 선택했습니다.',
        'policy':'허용 지연 이내이며 혼잡 통과 거리 1m 이상 감소 시 혼잡 회피, 그 외 최단시간. 후보 기반 분석용 규칙.',
        'time_bound_s':bound,
        'extra_time_s':max(0.,chosen['duration_s']-fastest['duration_s']),
        'busy_reduction_m':reduction,
        'busy_reduction_pct':100*reduction/fastest['busy_distance_m'] if fastest['busy_distance_m']>0 else None,
    }

class RouteService:
    def __init__(self, client_id, secret):
        from pyproj import Transformer
        from shapely.geometry import shape
        from shapely.ops import unary_union
        from shapely import transform
        self.client_id,self.secret=client_id,secret
        self.project=Transformer.from_crs(4326,5186,always_xy=True).transform
        import re
        html=(ROOT/'index.html').read_text()
        self.data=json.loads(re.search(r'<script id="route-data" type="application/json">(.*?)</script>',html,re.S)[1])
        self.areas={a['id']:transform(shape(a['geometry']),self.project,interleaved=False) for a in self.data['areas']}
        self.union=unary_union
        self._coverage=None
        self._busy_cache={}
    def search(self,body):
        query=str(body.get('query','')).strip()
        kind=body.get('kind','goal')
        if not 2<=len(query)<=120:raise ValueError('검색어를 2~120자로 입력하세요.')
        import re
        normalized=lambda x:re.sub(r'\s+','',''.join(str(x))).lower()
        q=normalized(query)
        local=self.data.get('stations',[]) if kind=='start' else [p for p in self.data.get('places',[])+self.data.get('stations',[]) if p.get('coords')]
        matches=[dict(x) for x in local if all(normalized(term) in normalized(x['name']+' '+x.get('address','')) for term in query.split())][:15]
        if matches or kind=='start':return {'results':matches,'source':'보유 거점·상권 이름 검색','note':'출발지는 공식 거점 이름으로 검색합니다.'}
        params=urlencode({'query':query,'count':10,'coordinate':'126.99,37.54'})
        req=Request('https://maps.apigw.ntruss.com/map-geocode/v2/geocode?'+params,headers={'X-NCP-APIGW-API-KEY-ID':self.client_id,'X-NCP-APIGW-API-KEY':self.secret,'Accept':'application/json'})
        with urlopen(req,timeout=20) as response:data=json.load(response)
        if data.get('status')!='OK':raise ValueError('주소 검색에 실패했습니다. Geocoding 선택을 확인하세요.')
        results=[]
        for a in data.get('addresses',[]):
            coords=[float(a['x']),float(a['y'])]
            if 126.7<=coords[0]<=127.3 and 37.4<=coords[1]<=37.75:
                results.append({'name':a.get('roadAddress') or a.get('jibunAddress'),'address':a.get('jibunAddress',''),'coords':coords,'source':'NAVER Geocoding address'})
        return {'results':results,'source':'NAVER 주소 검색','note':'일반 가게·장소명 검색은 지원하지 않습니다. 도로명 또는 지번 주소를 입력하세요.'}
    def request(self,start,goal,waypoint=None):
        params={'start':','.join(map(str,start)),'goal':','.join(map(str,goal)), 'option':'trafast:traoptimal:tracomfort'}
        if waypoint:params['waypoints']=','.join(map(str,waypoint))
        req=Request('https://maps.apigw.ntruss.com/map-direction/v1/driving?'+urlencode(params),headers={'X-NCP-APIGW-API-KEY-ID':self.client_id,'X-NCP-APIGW-API-KEY':self.secret})
        with urlopen(req,timeout=25) as response: data=json.load(response)
        if data.get('code')!=0:raise ValueError('네이버에서 경로를 찾지 못했습니다. 차량 접근 가능한 지점을 선택하세요.')
        return [dict(r,source=k) for k,items in data.get('route',{}).items() for r in items]
    def compare(self,body):
        from shapely.geometry import LineString,Point
        from shapely import transform
        start,goal=body['start'],body['goal']
        for p in (start,goal):
            if len(p)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in p) or not (126.7<=p[0]<=127.3 and 37.4<=p[1]<=37.75):raise ValueError('출발·도착 좌표는 서울 범위의 경도, 위도로 지정하세요.')
        hour=str(int(body.get('hour',18)));delay=float(body.get('delay',.1))
        if hour not in self.data['busy']:raise ValueError('지원하지 않는 혼잡 시간대입니다.')
        if not 0<=delay<=.5:raise ValueError('허용 지연은 0~50% 범위입니다.')
        # Scoring is limited to the commercial geometry actually in this project.
        if self._coverage is None:self._coverage=self.union(list(self.areas.values()))
        coverage=self._coverage
        if hour not in self._busy_cache:
            self._busy_cache[hour]=self.union([self.areas[k] for k in self.data['busy'][hour] if k in self.areas])
        busy=self._busy_cache[hour]
        routes=self.request(start,goal); calls=1; failures=0
        # Four deterministic offset waypoints generate alternatives; no artificial straight routes.
        mx,my=(start[0]+goal[0])/2,(start[1]+goal[1])/2
        # Same four alternatives, concurrent I/O; read results in a fixed order.
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(self.request,start,goal,[mx+dx,my+dy]) for dx,dy in [(0,.006),(0,-.006),(.008,0),(-.008,0)]]
            calls+=len(futures)
            for future in futures:
                try:routes+=future.result()
                except Exception:failures+=1
        candidates=[];seen=set()
        for r in routes:
            path=r.get('path',[])
            if len(path)<2:continue
            key=tuple(tuple(p) for p in path)
            if key in seen:continue
            seen.add(key); line=transform(LineString(path),self.project,interleaved=False);s=r['summary']
            candidates.append({'path':path,'distance_m':s['distance'],'duration_s':s['duration']/1000,'busy_distance_m':line.intersection(busy).length,'outside_commercial_area_m':line.difference(coverage).length,'source':r['source']})
        if not candidates:raise ValueError('유효한 경로가 없습니다.')
        shortest=min(candidates,key=lambda r:(r['distance_m'],r['duration_s']))
        fastest=min(candidates,key=lambda r:(r['duration_s'],r['distance_m']))
        allowed=[r for r in candidates if r['duration_s']<=fastest['duration_s']*(1+delay)]
        avoid=min(allowed,key=lambda r:(r['busy_distance_m'],r['duration_s']))
        chosen=[dict(r,kind=k) for k,r in zip(['distance','time','congestion_avoidance'],[shortest,fastest,avoid])]
        return {'recommendation':recommend_route(fastest,avoid,delay),'routes':chosen,'start':start,'goal':goal,'hour':hour,'delay':delay,'candidate_count':len(candidates),'api_calls':calls,'failed_alternative_calls':failures,'queried_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'same_paths':len({tuple(map(tuple,r['path'])) for r in chosen})==1,'busy_reduction_m':fastest['busy_distance_m']-avoid['busy_distance_m'],'extra_time_s':avoid['duration_s']-fastest['duration_s'],'time_saving_s':shortest['duration_s']-fastest['duration_s'],'method':'3 NAVER options + 4 offset waypoint queries; minimum among returned candidates, not global optimum','population_basis':'2026 Q1 historical area population; selected hour; NAVER duration is current traffic, not historical TOPIS'}

# 서울 상권 혼잡·119 접근 지도 — 웹용 사본

분석 원본·노트북·PDF·그림·글꼴·캐시를 제외한 웹 실행용 파일만 포함한다. 서울 1,649개 상권의 경계·6개 시간대 점수와 센터 목록은 `index.html`에 내장돼 있다. 사용하지 않는 기존 TOPIS 경로·거점 문맥 자료는 이 사본의 HTML에서만 제외했다. 원본 분석 프로젝트는 별도로 보존한다.

```text
index.html
scripts/
  serve_route_map.py
  naver_route_service.py
requirements.txt
네이버_경로비교_실행.command
.gitignore
README.md
```

## GitHub 업로드

이 폴더 **안의 7개 파일**을 저장소 최상위에 올린다. `scripts/` 하위 두 파일의 위치를 유지한다. 기존 분석 자료를 이미 올렸다면 이 사본에서 제외된 대용량 자료를 저장소에서 별도로 정리해야 저장소가 가벼워진다. 이 사본에는 비밀키가 없다.

## 로컬 실행

프로젝트 루트에서 다음 명령을 실행한다.

```sh
python3.12 -m venv .venv-route
.venv-route/bin/python -m pip install -r requirements.txt
.venv-route/bin/python scripts/serve_route_map.py --naver --port 8001
```

터미널에 같은 Maps Application의 Client ID와 Client Secret을 입력하고 http://localhost:8001/ 을 연다. Secret은 숨김 입력한다. 환경을 설치한 뒤에는 `.command` 파일로 실행해도 된다. 같은 Application에서 Web Dynamic Map·Directions 5·Geocoding을 활성화하고 서비스 URL은 `http://localhost`로 등록한다.

## Vercel 배포 범위

**이 폴더는 아직 Vercel Functions 구현을 포함하지 않는다.** 정적 HTML만 올려서는 `/api/config`, `/api/search`, `/api/compare`가 실행되지 않으므로 지도 인증 자동 연결·주소·경로 검색이 작동하지 않는다. Vercel에서 사용하려면 이 Python 서버를 배포용 API 함수로 옮기고 환경변수를 설정해야 한다. `index.html`에 Client Secret을 넣지 않는다.

상권 음영은 2026년 1분기 인구 기준이며 경로 시간은 현재 일반차량 교통 기준이다. 시간대 선택은 교통 예측 출발시각을 바꾸는 기능이 아니다.

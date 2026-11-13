# 서울 상권·119 지도 Vercel 배포

## 업로드 파일

최신 웹 전용 사본: `data/interim/github-upload/ABA_119_WEB/`.

```text
app.py                   # Vercel WSGI 진입점과 API
pyproject.toml           # Python 3.12, 의존성, app:app 명시
vercel.json              # Flask 및 함수 설정
.vercelignore            # 분석 원본·임시 파일 제외
index.html               # 지도·상권·센터·UI 내장
scripts/
  naver_route_service.py  # 거리·시간·혼잡 후보 평가
  serve_route_map.py      # 로컬 실행용 서버
requirements.txt
네이버_경로비교_실행.command
.gitignore
README.md
```

총 11개 파일을 GitHub 저장소 루트에 올린다. `.vercelignore`도 포함하며 숨김 파일은 Finder에서 `⌘ + Shift + .`로 볼 수 있다. `app.py`가 하위 폴더에 들어가지 않게 한다. 사본 갱신 명령은 `python3 scripts/prepare_web_upload.py`이다. 원본·노트북·PDF·이미지·글꼴은 포함하지 않는다.

## Vercel 설정

기존 정적 화면용 설정을 다음과 같이 변경한다.

| 항목 | 값 |
|---|---|
| Framework Preset | Flask |
| Root Directory | app.py와 index.html이 있는 저장소 루트 `./` |
| Build Command | Override 끄기, 기본값 |
| Output Directory | Override 끄기, 기본값 (`.` 직접 입력 제거) |
| Install Command | Override 끄기, 기본값 |

`pyproject.toml`에 `[tool.vercel] entrypoint = "app:app"`을 명시했다. `vercel.json`도 Flask를 지정한다. 기존 오류 `PYTHON_ENTRYPOINT_NOT_FOUND`는 로컬 서버만 있고 인식 가능한 Python 진입점이 없어서 발생했다. 새 `app.py`는 전역 WSGI 객체 `app`을 내보낸다.

## 인증키

Vercel 프로젝트의 **Settings → Environment Variables**에서 같은 NAVER Maps Application의 두 값을 등록한다.

| 이름 | 값 |
|---|---|
| NAVER_MAPS_CLIENT_ID | Client ID |
| NAVER_MAPS_CLIENT_SECRET | Client Secret |

Production에 적용하고 Preview에서도 쓸 경우 Preview도 선택한다. 저장 후 **Deployments → 최신 배포 → Redeploy**한다. 키 값은 GitHub 파일이나 채팅에 넣지 않는다. Client ID만 `/api/config`에서 브라우저로 제공하며 Secret은 서버에서만 사용한다.

네이버 콘솔의 같은 Application에서 **Web Dynamic Map·Directions 5·Geocoding**을 활성화하고, Web 서비스 URL에는 실제 운영 도메인(예: `https://프로젝트명.vercel.app`)을 추가한다. 포트와 경로는 제외한다. Preview의 별도 도메인은 자동으로 인증되지 않으므로 우선 고정 운영 도메인으로 확인한다.

## 확인

- `/`: 최종 지도 화면
- `/api/health`: `ok: true`, 두 환경변수 존재 여부 `configured`
- `/api/config`: 공개 Client ID 또는 설정 안내. Secret은 반환하지 않는다.
- `/api/search`: POST 주소·이름 검색
- `/api/compare`: POST 경로 후보 평가

Flask 테스트 클라이언트로 진입점, 설정 누락, Secret 비노출, JSON 검증, 검색·경로 호출 연결을 검증한다. 실제 Vercel 빌드·네이버 실키 인증 성공 여부는 사용자 재배포 후 확인해야 한다. 함수 제한 시간은 180초이며 적용 가능한 실행 시간은 Vercel 프로젝트 요금제·설정의 제한을 따른다.

상권 음영은 2026년 1분기 구역 인구이며 경로 시간은 현재 일반차량 교통이다. 시간대 선택은 네이버의 출발시각을 바꾸는 기능이 아니다. 세 경로가 같으면 그대로 표시한다. 한 번 경로 검색하면 최대 5회 네이버 API 요청이 발생할 수 있다.

## 로컬 실행

```sh
python3.12 -m venv .venv-route
.venv-route/bin/python -m pip install -r requirements.txt
.venv-route/bin/python scripts/serve_route_map.py --naver --port 8001
```

터미널에 같은 Application의 ID·Secret을 입력하고 http://localhost:8001/ 을 연다. 이미 설치했다면 `.command` 파일로 실행할 수 있다.

공식 문서: [Python 진입점](https://vercel.com/docs/functions/runtimes/python#python-entrypoints), [Flask 배포](https://vercel.com/docs/frameworks/backend/flask), [환경변수](https://vercel.com/docs/environment-variables).

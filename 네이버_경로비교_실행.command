#!/bin/zsh
cd "${0:A:h}"
./.venv-route/bin/python scripts/serve_route_map.py --naver --port 8001
printf '\n종료하려면 Enter를 누르세요.'
read

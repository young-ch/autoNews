#!/bin/bash
# ==============================================================================
# [MORNING] 글로벌 금융 모닝 브리핑 자동 실행 스크립트 (Linux 전용)
# ==============================================================================
# 스크립트 위치 디렉토리로 이동
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# 가상환경이 있다면 활성화 (선택 사항)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

mkdir -p logs

# 파이썬 실행 (화면 출력과 로그 파일 동시 기록)
python3 pipeline.py 2>&1 | tee -a logs/cron_morning.log


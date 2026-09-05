#!/bin/bash
# 일상/육아 트렌드 파이프라인 실행 스크립트

echo "=========================================="
echo "Running Daily Trend Pipeline..."
echo "=========================================="

# 스크립트가 있는 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경이 있다면 여기서 활성화하세요 (예: source venv/bin/activate)

# 파이썬 스크립트 실행
python3 daily_trend_pipeline.py

echo ""
echo "Pipeline Finished."

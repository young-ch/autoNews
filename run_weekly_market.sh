#!/bin/bash
# 주말 시황 파이프라인 실행 스크립트

echo "=========================================="
echo "Running Weekly Market Pipeline..."
echo "=========================================="

# 스크립트가 있는 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경이 있다면 여기서 활성화하세요 (예: source venv/bin/activate)

# 파이썬 스크립트 실행
python3 weekly_market_pipeline.py

echo ""
echo "Pipeline Finished."

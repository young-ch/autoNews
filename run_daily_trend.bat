@echo off
REM 일상/육아 트렌드 파이프라인 실행 스크립트
echo ==========================================
echo Running Daily Trend Pipeline...
echo ==========================================

REM 현재 디렉토리로 이동 (스크립트가 있는 위치 기준)
cd /d "%~dp0"

REM 파이썬 스크립트 실행 (환경에 맞게 python 경로 수정 필요 시 변경)
python daily_trend_pipeline.py

echo.
echo Pipeline Finished.
pause

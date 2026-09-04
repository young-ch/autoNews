@echo off
chcp 65001 > nul
echo =======================================================
echo [MORNING] 글로벌 금융 모닝 브리핑 자동화 파이프라인 가동...
echo =======================================================
cd /d "C:\Users\전산실PC_SS_091\Desktop\stock\blog"
python pipeline.py
echo.
echo 작업이 완료되었습니다.

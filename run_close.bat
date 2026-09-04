@echo off
chcp 65001 > nul
echo =======================================================
echo [CLOSE] 한국 증시 장마감 시황 자동화 파이프라인 가동...
echo =======================================================
cd /d "C:\Users\전산실PC_SS_091\Desktop\stock\blog"
python market_close_pipeline.py
echo.
echo 작업이 완료되었습니다.

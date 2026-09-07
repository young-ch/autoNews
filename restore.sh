#!/bin/bash
# ==============================================================================
# [RESTORE] 워드프레스 & MySQL 원클릭 전체 복원 스크립트 (Linux 전용)
# ==============================================================================
# 사용법: ./restore.sh [백업파일경로.tar.gz]
# 예  시: ./restore.sh backups/stock_blog_backup_20260907_120000.tar.gz
# ==============================================================================

if [ -z "$1" ]; then
    echo "사용법: ./restore.sh <백업_압축파일.tar.gz>"
    echo "예시: ./restore.sh backups/stock_blog_backup_20260907_120000.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[오류] 백업 파일을 찾을 수 없습니다: $BACKUP_FILE"
    exit 1
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================"
echo " [1/4] 백업 압축 파일 해제 중: $BACKUP_FILE"
echo "========================================================"
tar -xzvf "$BACKUP_FILE"

# 압축 해제된 SQL 파일 찾기
SQL_FILE=$(ls -t db_dump_*.sql 2>/dev/null | head -n 1)

if [ -z "$SQL_FILE" ]; then
    echo "[경고] 압축 파일 내에 db_dump_*.sql 파일이 없습니다."
else
    echo " -> 발견된 DB 덤프 파일: $SQL_FILE"
fi

echo ""
echo "========================================================"
echo " [2/4] 도커 서비스 구동 (MySQL & WordPress)..."
echo "========================================================"
docker compose up -d

echo " -> MySQL 컨테이너 구동 대기 (10초)..."
sleep 10

echo ""
echo "========================================================"
echo " [3/4] MySQL 데이터베이스 데이터 복원 중..."
echo "========================================================"
if [ -n "$SQL_FILE" ] && [ -f "$SQL_FILE" ]; then
    cat "$SQL_FILE" | docker exec -i stock_mysql mysql -u wp_user -pwp_password1234 stock_blog
    if [ $? -eq 0 ]; then
        echo " -> DB 데이터 복원 성공!"
        rm -f "$SQL_FILE"
    else
        echo " [오류] DB 데이터 복원 중 오류 발생!"
    fi
fi

echo ""
echo "========================================================"
echo " [4/4] 워드프레스 컨테이너 재시작..."
echo "========================================================"
docker compose restart wordpress

echo ""
echo "========================================================"
echo " ✅ 모든 복원 작업이 완료되었습니다!"
echo " 웹 브라우저에서 사이트가 정상 작동하는지 확인해 보세요."
echo "========================================================"

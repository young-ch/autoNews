#!/bin/bash
# ==============================================================================
# [BACKUP] 워드프레스 & MySQL 원클릭 전체 백업 스크립트 (Linux 전용)
# ==============================================================================
# 실행 방법: ./backup.sh
# 주기적 실행(크론탭 예시): 0 4 * * * /path/to/backup.sh > /dev/null 2>&1
# ==============================================================================

# 스크립트 위치 디렉토리로 이동
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

BACKUP_DIR="$DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TAR_FILE="stock_blog_backup_${TIMESTAMP}.tar.gz"
SQL_FILE="db_dump_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "========================================================"
echo " [1/3] MySQL 데이터베이스(stock_blog) 덤프 추출 시작..."
echo "========================================================"

# MySQL 컨테이너 내부에서 mysqldump 실행
if docker ps | grep -q "stock_mysql"; then
    docker exec stock_mysql mysqldump -u wp_user -pwp_password1234 stock_blog > "$BACKUP_DIR/$SQL_FILE"
    if [ $? -eq 0 ]; then
        echo " -> DB 덤프 완료: $BACKUP_DIR/$SQL_FILE"
    else
        echo " [오류] MySQL 덤프 실패! 컨테이너 상태와 계정 정보를 확인하세요."
        exit 1
    fi
else
    echo " [오류] 'stock_mysql' 도커 컨테이너가 실행 중이지 않습니다."
    exit 1
fi

echo ""
echo "========================================================"
echo " [2/3] 워드프레스 파일, DB 덤프, 도커 설정 전체 압축..."
echo "========================================================"

# wp_data (워드프레스 이미지/파일), docker-compose.yml, .env, DB덤프 압축
tar -czf "$BACKUP_DIR/$TAR_FILE" \
    --exclude="backups" \
    --exclude="logs" \
    --exclude="venv" \
    --exclude="__pycache__" \
    docker-compose.yml \
    .env \
    wp_data \
    -C "$BACKUP_DIR" "$SQL_FILE"

if [ $? -eq 0 ]; then
    FILE_SIZE=$(du -h "$BACKUP_DIR/$TAR_FILE" | cut -f1)
    echo " -> 전체 백업 완료: $BACKUP_DIR/$TAR_FILE ($FILE_SIZE)"
    # 압축에 포함되었으므로 임시 단독 sql 파일은 삭제 (필요시 보관 가능)
    rm -f "$BACKUP_DIR/$SQL_FILE"
else
    echo " [오류] 파일 압축 중 문제가 발생했습니다."
    exit 1
fi

echo ""
echo "========================================================"
echo " [3/3] 오래된 백업 파일 정리 (14일 초과 파일 자동 삭제)"
echo "========================================================"
find "$BACKUP_DIR" -name "stock_blog_backup_*.tar.gz" -mtime +14 -exec rm -f {} \;
echo " -> 14일 지난 구형 백업 정리 완료."

echo ""
echo "========================================================"
echo " ✅ 백업 성공!"
echo " 저장 위치: $BACKUP_DIR/$TAR_FILE"
echo " USB나 로컬 PC로 가져갈 때: scp 또는 FileZilla를 이용해 위 파일을 복사하세요."
echo "========================================================"

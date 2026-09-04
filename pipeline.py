"""
금융 시황 자동 수집 & 블로그 자동 임시저장 파이프라인 (Main Pipeline)
- 1단계: feedparser를 활용한 Google News RSS 최신 시황 기사 수집 (국내증시, 비트코인, 나스닥, 미국 에너지주)
- 2단계: Gemini API / OpenAI 금융 분석가 시스템 프롬프트 기반 가독성 높은 HTML 리포트 생성
- 3단계: 워드프레스 REST API / 티스토리 API를 통해 '임시 저장(Draft)' 상태로 자동 업로드
"""

import os
import sys
import logging
import datetime
import argparse
from typing import Dict, Any

# 모듈 임포트
import config
from collectors import collect_market_news
from processors import generate_market_report
from chart_generator import generate_market_thumbnail
from publishers import publish_draft_post

# 로깅 설정 (콘솔 및 파일 동시 출력)
def setup_logging():
    log_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 (logs 디렉토리에 일별 보관)
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"pipeline_{datetime.date.today().strftime('%Y%m%d')}.log")
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

logger = logging.getLogger("PipelineOrchestrator")


def run_pipeline(dry_run: bool = False) -> Dict[str, Any]:
    """
    3단계 파이프라인 전체를 순차적으로 실행합니다.
    
    Args:
        dry_run (bool): True일 경우 블로그 업로드를 생략하고 로컬 HTML 파일로만 저장합니다.
        
    Returns:
        Dict[str, Any]: 실행 결과 상태 요약
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    post_title = f"[{today_str}] 글로벌 금융 모닝 브리핑: 국내증시 · 비트코인 · 나스닥 · 미국에너지 시황"
    
    logger.info("=" * 70)
    logger.info(f"🚀 금융 시황 자동화 파이프라인 시작: {post_title}")
    logger.info("=" * 70)

    # -------------------------------------------------------------------------
    # [Step 1] 데이터 수집부 (Data Collection)
    # -------------------------------------------------------------------------
    logger.info("\n>>> [1단계] 최신 금융 뉴스 RSS 수집 시작...")
    try:
        articles = collect_market_news(
            keywords=config.DEFAULT_KEYWORDS,
            max_per_keyword=config.MAX_ARTICLES_PER_KEYWORD
        )
        if not articles:
            logger.warning("수집된 뉴스가 없습니다. 키워드 및 네트워크 연결을 확인해 주세요.")
        else:
            logger.info(f"총 {len(articles)}개의 최신 시황 기사가 성공적으로 수집되었습니다.")
    except Exception as e:
        logger.error(f"[1단계 실패] 뉴스 데이터 수집 도중 치명적 오류: {e}", exc_info=True)
        articles = []

    # -------------------------------------------------------------------------
    # [Step 2] AI 추론부 (AI Processing)
    # -------------------------------------------------------------------------
    logger.info("\n>>> [2단계] AI 금융 분석가 리포트(HTML) 생성 시작...")
    html_content = ""
    try:
        html_content = generate_market_report(articles)
        logger.info("AI 추론부 실행 완료: 블로그용 정제 HTML 생성 성공")
    except Exception as e:
        logger.error(f"[2단계 실패] AI 리포트 생성 도중 오류 발생: {e}", exc_info=True)
        html_content = f"<h1>{post_title}</h1><p>리포트 생성 중 오류가 발생했습니다: {e}</p>"

    # -------------------------------------------------------------------------
    # [Step 2.5] 썸네일 인포그래픽 이미지 자동 생성 (Thumbnail Generation)
    # -------------------------------------------------------------------------
    logger.info("\n>>> [2.5단계] 고해상도 시황 인포그래픽 썸네일 차트 생성 중...")
    thumbnail_path = None
    try:
        thumbnail_path = generate_market_thumbnail(today_str)
        logger.info(f"썸네일 차트 생성 완료: {thumbnail_path}")
    except Exception as e:
        logger.warning(f"썸네일 차트 생성 실패 (계속 진행): {e}")

    # 로컬 백업/미리보기 저장
    preview_path = os.path.join(os.path.dirname(__file__), "last_generated_report.html")
    try:
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"로컬 백업 및 미리보기 파일 저장 완료: {preview_path}")
    except Exception as e:
        logger.warning(f"로컬 미리보기 파일 저장 실패: {e}")

    # -------------------------------------------------------------------------
    # [Step 3] 자동 발행부 (Auto Publishing)
    # -------------------------------------------------------------------------
    if dry_run:
        logger.info("\n>>> [3단계 건너뜀] '--dry-run' 모드이므로 블로그 업로드를 실행하지 않습니다.")
        return {
            "status": "dry_run_success",
            "title": post_title,
            "articles_count": len(articles),
            "preview_file": preview_path,
            "thumbnail": thumbnail_path
        }

    logger.info("\n>>> [3단계] 블로그 '임시 저장(Draft)' 상태 업로드 시작...")
    publish_result = {}
    try:
        publish_result = publish_draft_post(
            title=post_title,
            html_content=html_content,
            image_path=thumbnail_path
        )
        if publish_result.get("success"):
            logger.info(f"🎉 성공적으로 임시 저장되었습니다! 결과: {publish_result.get('message')}")
        else:
            logger.warning(f"⚠️ 임시 저장 실패/보류: {publish_result.get('message')}")
    except Exception as e:
        logger.error(f"[3단계 실패] 블로그 업로드 도중 오류 발생: {e}", exc_info=True)
        publish_result = {"success": False, "error": str(e)}


    logger.info("\n" + "=" * 70)
    logger.info("🏁 전체 파이프라인 프로세스 종료")
    logger.info("=" * 70)
    
    return {
        "status": "completed",
        "title": post_title,
        "articles_count": len(articles),
        "publish_result": publish_result,
        "preview_file": preview_path
    }


def main():
    """메인 엔트리포인트 함수"""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="금융 시황 자동 수집 및 블로그 임시저장 파이프라인")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="블로그에 업로드하지 않고 데이터 수집 및 로컬 HTML 생성만 테스트합니다."
    )
    args = parser.parse_args()

    run_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

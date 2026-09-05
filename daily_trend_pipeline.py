import os
import datetime
import logging
import config
from collectors import collect_trend_news
from processors import generate_trend_report
from publishers import publish_draft_post

logger = logging.getLogger("DailyTrendPipeline")

def run_daily_trend_pipeline():
    """일상/육아 트렌드 파이프라인 실행"""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    post_title = f"[{today_str}] 요새 핫한 육아템 & 일상 트렌드 TOP 3 💡"

    logger.info("=" * 70)
    logger.info(f"🚀 일상/육아 트렌드 파이프라인 시작: {post_title}")
    logger.info("=" * 70)

    # 1. 데이터 수집
    logger.info("\n>>> [1단계] 트렌드 뉴스 수집 시작...")
    articles = collect_trend_news(max_per_keyword=2)
    if not articles:
        logger.warning("수집된 뉴스가 없습니다.")

    # 2. AI 리포트 생성
    logger.info("\n>>> [2단계] AI 초안 리포트 생성 중...")
    html_content = generate_trend_report(articles)
    logger.info(f"리포트 생성 완료 (글자 수: {len(html_content)}자)")

    # 3. 워드프레스 업로드
    logger.info("\n>>> [3단계] 워드프레스 업로드 중...")
    result = publish_draft_post(
        title=post_title,
        html_content=html_content,
        category_id=config.DAILY_TREND_CATEGORY_ID
    )
    logger.info(f"결과: {result.get('message')}")
    
    if result.get("success"):
        wp_post_id = result.get("wp_result", {}).get("id") or result.get("id")
        try:
            from notifiers import send_telegram_message
            msg = f"🛒 <b>일상/육아 트렌드 초안 작성 완료!</b>\n\n결과: {result.get('message')}\n\n아래 버튼을 눌러 승인(발행)하거나, 편집기에 들어가서 <b>사장님의 실제 후기나 쿠팡 파트너스 링크</b>를 삽입하고 직접 발행해주세요."
            send_telegram_message(msg, post_id=wp_post_id)
            
            if wp_post_id:
                from telegram_listener import wait_for_approval
                wait_for_approval(post_id=wp_post_id, timeout_minutes=60)
        except Exception as e:
            logger.error(f"텔레그램 알림 발송/대기 실패: {e}")

    logger.info("=" * 70)
    logger.info("🏁 일상/육아 트렌드 파이프라인 완료!")
    logger.info("=" * 70)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_daily_trend_pipeline()

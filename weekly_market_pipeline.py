import os
import datetime
import logging
import config
from collectors import collect_us_market_news, fetch_us_sectors, fetch_us_macro
from processors import generate_weekly_market_report
from publishers import publish_draft_post

logger = logging.getLogger("WeeklyMarketPipeline")

def run_weekly_market_pipeline():
    """주말 시황 총정리 파이프라인 실행"""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    post_title = f"[{today_str}] 주말 결산: 이번 주 미국 증시 요약 및 다음 주 핵심 일정 📊"

    logger.info("=" * 70)
    logger.info(f"🚀 주말 시황 파이프라인 시작: {post_title}")
    logger.info("=" * 70)

    # 1. 데이터 수집
    logger.info("\n>>> [1단계] 주간 시황 데이터 수집 시작...")
    try:
        articles = collect_us_market_news(max_per_keyword=3)
        us_sectors = fetch_us_sectors()
        us_macro = fetch_us_macro()
    except Exception as e:
        logger.error(f"데이터 수집 실패: {e}")
        articles, us_sectors, us_macro = [], [], {}

    # 경제 캘린더 수집 (다음 주 프리뷰용 - test.saemaul.or.kr)
    economic_calendar = []
    try:
        import requests
        saemaul_url = os.getenv("SAEMAUL_SERVER_URL", "https://stock.marsticker.com").rstrip("/")
        r = requests.get(f"{saemaul_url}/api/economic-calendar", timeout=5)
        if r.status_code == 200:
            cal_data = r.json().get("data", [])
            # 이번 주/다음 주 일정 중 중요도 높은 것들만 추출 (여기서는 단순 중요도 순 정렬)
            important_events = [it for it in cal_data if it.get("importance", -1) >= 0]
            important_events.sort(key=lambda x: x.get("importance", -1), reverse=True)
            economic_calendar = important_events[:10]
    except Exception as e:
        logger.warning(f"경제 캘린더 수집 실패: {e}")

    # 2. AI 리포트 생성
    logger.info("\n>>> [2단계] AI 초안 리포트 생성 중...")
    html_content = generate_weekly_market_report(
        articles=articles,
        us_sectors=us_sectors,
        us_macro=us_macro,
        economic_calendar=economic_calendar
    )
    logger.info(f"리포트 생성 완료 (글자 수: {len(html_content)}자)")

    # 3. 워드프레스 업로드
    logger.info("\n>>> [3단계] 워드프레스 업로드 중...")
    result = publish_draft_post(
        title=post_title,
        html_content=html_content,
        category_id=config.WEEKLY_CATEGORY_ID
    )
    logger.info(f"결과: {result.get('message')}")
    
    if result.get("success"):
        wp_post_id = result.get("wp_result", {}).get("id") or result.get("id")
        try:
            from notifiers import send_telegram_message
            msg = f"📊 <b>주말 시황 초안 작성 완료!</b>\n\n결과: {result.get('message')}\n\n아래 버튼을 눌러 승인(발행)하거나, 편집기에 들어가서 <b>사장님의 주간 코멘트와 전략</b>을 작성 후 발행해주세요."
            send_telegram_message(msg, post_id=wp_post_id)
            
            if wp_post_id:
                from telegram_listener import wait_for_approval
                wait_for_approval(post_id=wp_post_id, timeout_minutes=60)
        except Exception as e:
            logger.error(f"텔레그램 알림 발송/대기 실패: {e}")

    logger.info("=" * 70)
    logger.info("🏁 주말 시황 파이프라인 완료!")
    logger.info("=" * 70)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_weekly_market_pipeline()

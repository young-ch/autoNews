"""
알림 모듈 (Notifiers Module)
- 텔레그램 등을 통해 사용자에게 처리 결과 및 편집기 링크 전송
"""

import logging
import requests
import config

logger = logging.getLogger(__name__)

def send_telegram_message(message: str) -> bool:
    """
    텔레그램 봇 API를 사용하여 사용자에게 메시지를 전송합니다.
    """
    bot_token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID

    if not bot_token or not chat_id:
        logger.warning("텔레그램 토큰(TELEGRAM_BOT_TOKEN) 또는 챗아이디(TELEGRAM_CHAT_ID)가 설정되지 않아 알림을 생략합니다.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("텔레그램 알림 전송 성공!")
            return True
        else:
            logger.error(f"텔레그램 알림 전송 실패 (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"텔레그램 전송 중 예외 발생: {e}")
        return False

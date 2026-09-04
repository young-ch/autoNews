"""
텔레그램 승인 대기(Polling) 모듈
- 스크립트 실행 마지막에 호출되어 최대 1시간 동안 사장님의 '승인' 버튼 클릭을 기다립니다.
"""

import time
import logging
import requests
import config
from publishers import approve_and_publish_wordpress
from notifiers import send_telegram_message

logger = logging.getLogger(__name__)

def wait_for_approval(post_id: str, timeout_minutes: int = 60) -> bool:
    """
    지정된 시간(분) 동안 텔레그램 getUpdates를 폴링하며 승인 버튼 클릭을 기다립니다.
    버튼이 클릭되면 워드프레스 발행 함수를 호출하고 True를 반환합니다.
    시간이 초과되면 False를 반환하고 종료합니다.
    """
    bot_token = config.TELEGRAM_BOT_TOKEN
    
    if not bot_token or not post_id:
        return False
        
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    # 이전에 쌓인 메시지를 무시하기 위해 최근 update_id를 가져옴
    last_update_id = None
    try:
        init_res = requests.get(url, timeout=10).json()
        if init_res.get("ok") and init_res.get("result"):
            last_update_id = init_res["result"][-1]["update_id"]
    except Exception:
        pass
        
    logger.info(f"⏳ 텔레그램 승인 대기 시작 (최대 {timeout_minutes}분 대기)...")
    
    end_time = time.time() + (timeout_minutes * 60)
    
    while time.time() < end_time:
        try:
            params = {"timeout": 10}
            if last_update_id:
                params["offset"] = last_update_id + 1
                
            res = requests.get(url, params=params, timeout=15)
            data = res.json()
            
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"]
                    
                    if "callback_query" in update:
                        callback_data = update["callback_query"].get("data", "")
                        callback_id = update["callback_query"].get("id")
                        
                        # 내 버튼인지 확인
                        if callback_data == f"approve_wp_{post_id}":
                            logger.info("✅ 텔레그램 승인 버튼 클릭 감지!")
                            
                            # 콜백 응답 (텔레그램 버튼 로딩 멈춤)
                            ans_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
                            requests.post(ans_url, json={"callback_query_id": callback_id, "text": "발행을 시작합니다!"})
                            
                            # 워드프레스 발행 (임시저장 -> 공개)
                            success = approve_and_publish_wordpress(post_id)
                            
                            if success:
                                send_telegram_message(f"🎉 <b>발행 완료!</b>\n\n워드프레스에 포스팅이 전체 공개로 발행되었습니다.")
                            else:
                                send_telegram_message(f"❌ <b>발행 실패!</b>\n\n워드프레스 발행 중 오류가 발생했습니다. 로그를 확인해주세요.")
                                
                            return success
                            
        except requests.exceptions.RequestException:
            pass # 통신 일시 오류 무시
        except Exception as e:
            logger.error(f"폴링 중 오류: {e}")
            
        time.sleep(3) # 3초 간격 폴링
        
    logger.info("⏰ 승인 대기 시간(1시간)이 초과되어 대기를 종료합니다. (글은 임시저장 상태로 유지됩니다)")
    return False

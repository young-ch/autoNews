import os
import time
import logging
import requests
import datetime
from PIL import Image
from urllib.parse import urljoin
from logging.handlers import RotatingFileHandler

# 사용자 모듈 임포트
import config
from processors import generate_daily_life_post
from publishers import publish_draft_post, approve_and_publish_wordpress
from notifiers import send_telegram_message

# ==========================================
# 1. 로깅 설정
# ==========================================
log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
log_handler = RotatingFileHandler('telegram_bot.log', maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
log_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
CHAT_ID = config.TELEGRAM_CHAT_ID

if not BOT_TOKEN or not CHAT_ID:
    logger.error("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 .env에 설정되지 않았습니다.")
    exit(1)

# ==========================================
# 2. 텔레그램 봇 유틸리티 함수
# ==========================================
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(url, params=params, timeout=40)
        return response.json()
    except Exception as e:
        logger.warning(f"getUpdates 오류: {e}")
        return {}

def download_telegram_photo(file_id: str) -> str:
    """
    텔레그램 서버에서 사진을 다운로드하여 로컬 임시 폴더에 저장합니다.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    try:
        res = requests.get(url, params={"file_id": file_id}).json()
        if not res.get("ok"):
            logger.error(f"getFile 실패: {res}")
            return None
            
        file_path = res["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        
        img_res = requests.get(download_url)
        if img_res.status_code == 200:
            os.makedirs("temp_images", exist_ok=True)
            ext = file_path.split(".")[-1]
            local_path = f"temp_images/photo_{int(time.time())}.{ext}"
            
            with open(local_path, 'wb') as f:
                f.write(img_res.content)
                
            # 워드프레스 용량 제한(보통 2MB)을 피하기 위해 리사이즈 및 압축
            try:
                with Image.open(local_path) as img:
                    img = img.convert("RGB")
                    img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
                    img.save(local_path, "JPEG", quality=80)
                logger.info(f"이미지 압축 완료: {local_path}")
            except Exception as e:
                logger.warning(f"이미지 압축 실패 (원본 사용): {e}")
            
            logger.info(f"사진 다운로드 준비 완료: {local_path}")
            return local_path
    except Exception as e:
        logger.error(f"사진 다운로드 중 오류: {e}")
    return None

def answer_callback_query(callback_query_id: str, text: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id, "text": text})

def send_message(text: str, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

# ==========================================
# 3. 메시지 처리 로직
# ==========================================
def handle_photo_message(message: dict):
    logger.info("사진 메시지가 수신되었습니다. 일상/육아 파이프라인을 시작합니다.")
    send_message("📸 사진을 확인했습니다! AI가 사진을 분석하여 블로그 초안을 작성 중입니다. (약 30초 소요)")
    
    # 텔레그램은 여러 해상도의 사진을 배열로 보냅니다. 가장 큰 사진(마지막 요소) 선택
    photos = message.get("photo", [])
    if not photos:
        return
        
    best_photo = photos[-1]
    file_id = best_photo["file_id"]
    caption = message.get("caption", "")
    
    local_img_path = download_telegram_photo(file_id)
    if not local_img_path:
        send_message("❌ 사진 다운로드에 실패했습니다.")
        return
        
    try:
        # 1. AI 초안 생성 (Gemini Vision)
        html_content = generate_daily_life_post(image_path=local_img_path, user_caption=caption)
        
        # 2. 제목 생성
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        title_hint = caption[:15] + "..." if caption else "일상 기록"
        post_title = f"[{today_str}] 나의 {title_hint} 📝"
        
        # 3. 워드프레스 업로드 (임시저장 & 대표 이미지 설정)
        logger.info("워드프레스에 초안 및 사진 업로드 중...")
        result = publish_draft_post(
            title=post_title,
            html_content=html_content,
            category_id=config.DAILY_TREND_CATEGORY_ID,
            image_path=local_img_path
        )
        
        if result.get("success"):
            post_id = result.get("wp_result", result).get("id", "")
            if post_id:
                # 4. 텔레그램으로 승인/수정 링크 전송
                edit_link = f"{config.WORDPRESS_URL}/wp-admin/post.php?post={post_id}&action=edit"
                # 공용 도메인으로 치환 (marsticker)
                if "localhost" in edit_link or "127.0.0.1" in edit_link:
                    edit_link = f"https://www.marsticker.com/wp-admin/post.php?post={post_id}&action=edit"
                    
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ 내용 수정/추가하기", "url": edit_link}],
                        [{"text": "✅ 이대로 즉시 발행하기 (승인)", "callback_data": f"approve_wp_{post_id}"}]
                    ]
                }
                send_message(
                    f"🎉 <b>포스팅 초안이 완성되었습니다!</b>\n\n"
                    f"📝 <b>제목:</b> {post_title}\n\n"
                    f"아래 [내용 수정] 버튼을 눌러 하단에 사장님의 느낀점을 추가하신 뒤 발행하시거나, [즉시 발행하기]를 눌러 바로 업로드하세요!",
                    reply_markup=keyboard
                )
        else:
            send_message(f"❌ 워드프레스 업로드 실패: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"사진 처리 중 오류: {e}")
        send_message(f"❌ AI 분석 또는 업로드 중 오류가 발생했습니다: {str(e)}")

def handle_callback_query(callback_query: dict):
    data = callback_query.get("data", "")
    query_id = callback_query.get("id")
    
    if data.startswith("approve_wp_"):
        post_id = data.split("_")[-1]
        logger.info(f"워드프레스 승인 버튼 클릭됨 (Post ID: {post_id})")
        
        success = approve_and_publish_wordpress(post_id)
        if success:
            answer_callback_query(query_id, "✅ 승인 완료! 블로그에 공개 발행되었습니다.")
            send_message(f"✅ 글 ID: {post_id} - 블로그에 공개 발행이 완료되었습니다!")
        else:
            answer_callback_query(query_id, "❌ 발행 실패!")
            send_message("❌ 워드프레스 발행 중 오류가 발생했습니다. 로그를 확인해주세요.")

# ==========================================
# 4. 메인 루프 (데몬)
# ==========================================
def main():
    logger.info("🚀 텔레그램 봇 데몬이 시작되었습니다. 사진이나 승인 버튼 입력을 대기합니다...")
    
    # 시작할 때 쌓여있는 이전 메시지 무시
    offset = None
    try:
        init_data = get_updates(offset=None)
        if init_data.get("ok") and init_data.get("result"):
            offset = init_data["result"][-1]["update_id"] + 1
    except:
        pass

    while True:
        try:
            updates = get_updates(offset=offset)
            if updates.get("ok") and updates.get("result"):
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    
                    # 1. 사진 메시지 처리 (일반 사진 전송)
                    if "message" in update:
                        msg = update["message"]
                        # 본인이 보낸 메시지만 처리
                        if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
                            continue
                            
                        if "photo" in msg:
                            handle_photo_message(msg)
                        elif "document" in msg and msg["document"].get("mime_type", "").startswith("image/"):
                            # 원본 화질(파일)로 전송한 이미지 처리
                            # document 구조를 photo 배열과 비슷하게 임시 변환
                            msg["photo"] = [msg["document"]]
                            handle_photo_message(msg)
                        elif "text" in msg:
                            text = msg["text"]
                            if text == "/start" or text == "/help":
                                send_message("안녕하세요! 사장님의 일상 봇입니다.\n\n📸 <b>사진을 보내주시면</b> 즉시 AI가 일상/육아 블로그 초안을 작성하여 워드프레스에 임시저장해 드립니다!\n\n(사진 밑에 '오늘 점심은 갈비탕' 처럼 짧은 텍스트(캡션)를 같이 적어보내시면 더 좋습니다.)")
                    
                    # 2. 버튼 클릭(콜백) 처리
                    elif "callback_query" in update:
                        cb = update["callback_query"]
                        if str(cb.get("message", {}).get("chat", {}).get("id")) != str(CHAT_ID):
                            continue
                        handle_callback_query(cb)
                        
            time.sleep(1)
        except Exception as e:
            logger.error(f"메인 루프 에러: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

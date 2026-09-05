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
from publishers import upload_media_to_wordpress, publish_draft_post, approve_and_publish_wordpress
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
    # long polling timeout을 2초로 단축하여 미디어 그룹 검사 루프가 블로킹되지 않도록 개선
    params = {"timeout": 2, "allowed_updates": ["message", "callback_query"]}
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(url, params=params, timeout=5)
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
                
            # 워드프레스 용량 제한 및 Gemini API 속도 향상을 위해 더 작게 리사이즈 및 압축
            try:
                with Image.open(local_path) as img:
                    img = img.convert("RGB")
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                    img.save(local_path, "JPEG", quality=70)
                logger.info(f"이미지 압축 완료(800x800): {local_path}")
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
def handle_photo_messages(photos: list, caption: str):
    logger.info(f"사진 메시지 수신 (총 {len(photos)}장). 일상/육아 파이프라인 시작.")
    send_message(f"📸 {len(photos)}장의 사진을 확인했습니다! AI가 문맥에 맞게 사진을 배치하여 블로그 초안을 작성 중입니다. (약 30~60초 소요)")
    
    local_img_paths = []
    for photo in photos:
        file_id = photo.get("file_id")
        if file_id:
            path = download_telegram_photo(file_id)
            if path:
                local_img_paths.append(path)
                
    if not local_img_paths:
        send_message("❌ 사진 다운로드에 실패했습니다.")
        return
        
    try:
        # 워드프레스에 사진들을 먼저 업로드하여 URL 확보
        logger.info("워드프레스에 이미지 선제적 업로드 중...")
        image_urls = []
        featured_media_id = None
        for i, path in enumerate(local_img_paths):
            media_res = upload_media_to_wordpress(path)
            if isinstance(media_res, dict):
                image_urls.append(media_res.get("url"))
                if i == 0:
                    featured_media_id = media_res.get("id")
            else:
                image_urls.append(None)
                if i == 0:
                    featured_media_id = media_res

        # 1. AI 초안 생성 (Gemini Vision) - 여러 장 전달
        html_content = generate_daily_life_post(
            image_paths=local_img_paths, 
            user_caption=caption,
            image_urls=image_urls
        )
        
        # 2. 제목 생성
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        title_hint = caption[:15] + "..." if caption else "일상 기록"
        post_title = f"[{today_str}] 나의 {title_hint} 📝"
        
        # 3. 워드프레스 업로드 (임시저장)
        # 이미 썸네일(featured_media_id)을 확보했으므로 publish_to_wordpress를 직접 호출하거나
        # publish_draft_post를 우회하여 사용. publish_draft_post는 내부적으로 다시 업로드를 시도하므로
        # 여기서는 워드프레스 REST API로 바로 페이로드를 쏩니다.
        
        wp_url = config.WORDPRESS_URL
        wp_user = config.WORDPRESS_USER
        wp_app_pwd = config.WORDPRESS_APP_PASSWORD
        
        payload = {
            "title": post_title,
            "content": html_content,
            "status": "draft",
            "categories": [int(config.DAILY_TREND_CATEGORY_ID)] if config.DAILY_TREND_CATEGORY_ID else []
        }
        if featured_media_id:
            payload["featured_media"] = featured_media_id
            
        from publishers import WORKING_REST_PREFIX
        if WORKING_REST_PREFIX:
            endpoints_to_try = [f"{wp_url}{WORKING_REST_PREFIX}/posts"]
        else:
            endpoints_to_try = [
                f"{wp_url}/wp-json/wp/v2/posts",
                f"{wp_url}/index.php?rest_route=/wp/v2/posts"
            ]

        res = None
        for endpoint in endpoints_to_try:
            res = requests.post(endpoint, json=payload, auth=(wp_user, wp_app_pwd), timeout=30)
            if res.status_code != 404:
                break
        
        if res is not None and res.status_code in (200, 201):
            post_id = res.json().get("id")
            # 4. 텔레그램으로 승인/수정 링크 전송
            edit_link = f"{config.WORDPRESS_URL}/wp-admin/post.php?post={post_id}&action=edit"
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
                f"여러 장의 사진이 본문 중간중간에 예쁘게 들어갔습니다.\n"
                f"아래 [내용 수정] 버튼을 눌러 모바일에서 하단 찐후기만 적으신 뒤 발행하시거나, [즉시 발행하기]를 눌러 바로 업로드하세요!",
                reply_markup=keyboard
            )
        else:
            err_text = res.text[:100] if res is not None else "응답 없음"
            send_message(f"❌ 워드프레스 본문 업로드 실패: {err_text}")
            
    except Exception as e:
        logger.error(f"사진 처리 중 오류: {e}", exc_info=True)
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

    pending_media_groups = {} # media_group_id -> {"photos": [...], "caption": "", "time": float}

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
                            
                        # document로 원본 전송 시 변환
                        if "document" in msg and msg["document"].get("mime_type", "").startswith("image/"):
                            msg["photo"] = [msg["document"]]
                            
                        if "photo" in msg:
                            best_photo = msg["photo"][-1]
                            mg_id = msg.get("media_group_id")
                            caption = msg.get("caption", "")
                            
                            if mg_id:
                                if mg_id not in pending_media_groups:
                                    pending_media_groups[mg_id] = {"photos": [], "caption": "", "time": time.time()}
                                pending_media_groups[mg_id]["photos"].append(best_photo)
                                if caption:
                                    pending_media_groups[mg_id]["caption"] = caption
                                # 타이머는 최초 1번만 시작하거나 갱신하지 않음.
                            else:
                                # 단일 사진
                                handle_photo_messages([best_photo], caption)
                                
                        elif "text" in msg:
                            text = msg["text"]
                            if text == "/start" or text == "/help":
                                send_message("안녕하세요! 사장님의 일상 봇입니다.\n\n📸 <b>사진을 보내주시면</b> 즉시 AI가 사진을 여러 장 묶어서 완벽한 하나의 HTML 글로 만들어 드립니다!\n\n(첫 번째 사진에 '오늘 점심은 갈비탕' 처럼 캡션을 달아보세요.)")
                    
                    # 2. 버튼 클릭(콜백) 처리
                    elif "callback_query" in update:
                        cb = update["callback_query"]
                        if str(cb.get("message", {}).get("chat", {}).get("id")) != str(CHAT_ID):
                            continue
                        handle_callback_query(cb)
                        
            # 버퍼에 있는 미디어 그룹 타임아웃 검사 (1.5초 대기)
            current_time = time.time()
            for mg_id in list(pending_media_groups.keys()):
                if current_time - pending_media_groups[mg_id]["time"] > 1.5:
                    group = pending_media_groups.pop(mg_id)
                    handle_photo_messages(group["photos"], group["caption"])

            time.sleep(1)
        except Exception as e:
            logger.error(f"메인 루프 에러: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

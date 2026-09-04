"""
자동 발행부 (Auto Publishing Module)
- 워드프레스 REST API 및 티스토리 API를 통한 포스팅 자동 업로드
- [매우 중요] 즉시 발행(publish) 대신 '임시 저장(draft)' 상태로 등록
- 예외 발생 시 안전한 에러 핸들링 및 상세 로깅
"""

import logging
import datetime
from typing import Dict, Any, Optional
import os
import requests
from requests.auth import HTTPBasicAuth
import config

logger = logging.getLogger(__name__)


def upload_media_to_wordpress(image_path: str) -> Optional[int]:
    """
    워드프레스 미디어 라이브러리에 이미지를 업로드하고 attachment ID를 반환합니다.
    """
    if not image_path or not os.path.exists(image_path):
        return None

    wp_url = config.WORDPRESS_URL
    wp_user = config.WORDPRESS_USER
    wp_app_pwd = config.WORDPRESS_APP_PASSWORD

    if not wp_url or not wp_user or not wp_app_pwd:
        return None

    endpoints_to_try = [
        f"{wp_url}/wp-json/wp/v2/media",
        f"{wp_url}/index.php?rest_route=/wp/v2/media"
    ]
    filename = os.path.basename(image_path)

    try:
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()

        headers = {
            "Content-Type": "image/png",
            "Content-Disposition": f'attachment; filename="{filename}"'
        }

        logger.info(f"워드프레스 미디어 라이브러리에 썸네일 이미지 업로드 중... ({filename})")
        
        response = None
        for endpoint in endpoints_to_try:
            response = requests.post(
                endpoint,
                data=img_data,
                headers=headers,
                auth=HTTPBasicAuth(wp_user, wp_app_pwd),
                timeout=30
            )
            if response.status_code != 404:
                break
            logger.info(f"엔드포인트 {endpoint} 404 반환. 대체 REST 경로로 재시도합니다.")

        if response is not None and response.status_code in (200, 201):
            media_data = response.json()
            media_id = media_data.get("id")
            logger.info(f"미디어 업로드 성공! (Media ID: {media_id})")
            return media_id
        else:
            status_code = response.status_code if response is not None else "Unknown"
            resp_text = response.text[:200] if response is not None else ""
            logger.warning(f"미디어 업로드 응답 실패 (HTTP {status_code}): {resp_text}")
            return None
    except Exception as e:
        logger.warning(f"미디어 업로드 중 예외 발생: {e}")
        return None


def publish_to_wordpress(
    title: str,
    html_content: str,
    category_id: Optional[str] = None,
    image_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    워드프레스 REST API를 사용하여 글을 '임시 저장(draft)' 상태로 업로드합니다.
    이미지 경로가 제공되면 대표 특성 이미지(Featured Image)로 자동 등록합니다.
    """
    wp_url = config.WORDPRESS_URL
    wp_user = config.WORDPRESS_USER
    wp_app_pwd = config.WORDPRESS_APP_PASSWORD

    if not wp_url or not wp_user or not wp_app_pwd:
        error_msg = (
            "워드프레스 연동 정보(WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD)가 "
            ".env 파일에 완전하게 설정되지 않았습니다."
        )
        logger.error(error_msg)
        return {"success": False, "message": error_msg}

    # 1. 썸네일 이미지가 있으면 미디어 업로드 먼저 진행
    featured_media_id = None
    if image_path and os.path.exists(image_path):
        featured_media_id = upload_media_to_wordpress(image_path)

    endpoints_to_try = [
        f"{wp_url}/wp-json/wp/v2/posts",
        f"{wp_url}/index.php?rest_route=/wp/v2/posts"
    ]
    logger.info(f"워드프레스 REST API 엔드포인트 호출 준비: {endpoints_to_try[0]}")

    # 발행 상태 설정 (기본값: 'draft', .env에서 'publish'로 변경 시 즉시 발행)
    post_status = config.WORDPRESS_POST_STATUS if config.WORDPRESS_POST_STATUS in ("draft", "publish") else "draft"
    payload = {
        "title": title,
        "content": html_content,
        "status": post_status,
    }

    if featured_media_id:
        payload["featured_media"] = featured_media_id
        logger.info(f"포스팅의 대표 썸네일(featured_media)로 ID {featured_media_id} 연결 완료")

    # 카테고리 ID 지정 시 추가
    cat_id = category_id or config.WORDPRESS_CATEGORY_ID
    if cat_id:
        try:
            payload["categories"] = [int(cat_id)]
        except ValueError:
            logger.warning(f"카테고리 ID '{cat_id}'가 숫자가 아니므로 제외하고 전송합니다.")

    try:
        # 워드프레스 Application Password를 사용한 HTTP Basic Auth 인증
        response = None
        for endpoint in endpoints_to_try:
            response = requests.post(
                endpoint,
                json=payload,
                auth=HTTPBasicAuth(wp_user, wp_app_pwd),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            if response.status_code != 404:
                break
            logger.info(f"엔드포인트 {endpoint} 404 반환. 대체 REST 경로로 재시도합니다.")

        if response is not None and response.status_code in (200, 201):
            data = response.json()
            post_id = data.get("id")
            admin_link = f"{wp_url}/wp-admin/post.php?post={post_id}&action=edit"
            success_msg = f"워드프레스에 임시 저장(Draft) 완료!\n- 글 ID: {post_id}\n- 편집/미리보기 링크: {admin_link}"
            logger.info(success_msg.replace('\n', ' '))
            return {
                "success": True,
                "platform": "wordpress",
                "id": post_id,
                "link": admin_link,
                "status": "draft",
                "message": success_msg
            }
        elif response.status_code in (401, 403):
            err = (
                f"워드프레스 인증 실패 (상태 코드 {response.status_code}). "
                "워드프레스 관리자 -> 사용자 -> 프로필에서 생성한 '애플리케이션 비밀번호'와 사용자명을 확인하세요."
            )
            logger.error(err)
            return {"success": False, "platform": "wordpress", "status_code": response.status_code, "message": err}
        else:
            err = f"워드프레스 업로드 실패 (HTTP {response.status_code}): {response.text[:300]}"
            logger.error(err)
            return {"success": False, "platform": "wordpress", "status_code": response.status_code, "message": err}

    except requests.exceptions.Timeout:
        err = "워드프레스 서버 응답 시간 초과(Timeout - 30초)"
        logger.error(err)
        return {"success": False, "platform": "wordpress", "message": err}
    except requests.exceptions.ConnectionError as e:
        err = f"워드프레스 서버 연결 실패 (URL을 확인하세요): {e}"
        logger.error(err)
        return {"success": False, "platform": "wordpress", "message": err}
    except Exception as e:
        err = f"워드프레스 업로드 중 예기치 않은 오류 발생: {e}"
        logger.error(err, exc_info=True)
        return {"success": False, "platform": "wordpress", "message": err}


def publish_to_tistory(title: str, html_content: str) -> Dict[str, Any]:
    """
    티스토리 Open API를 사용하여 글을 '비공개/임시저장(visibility=0)' 상태로 업로드합니다.
    """
    access_token = config.TISTORY_ACCESS_TOKEN
    blog_name = config.TISTORY_BLOG_NAME

    if not access_token or not blog_name:
        error_msg = "티스토리 연동 정보(TISTORY_ACCESS_TOKEN, TISTORY_BLOG_NAME)가 설정되지 않았습니다."
        logger.error(error_msg)
        return {"success": False, "message": error_msg}

    api_url = "https://www.tistory.com/apis/post/write"
    
    # [중요] visibility=0 (0: 비공개/임시저장, 1: 보호, 3: 발행)
    payload = {
        "access_token": access_token,
        "output": "json",
        "blogName": blog_name,
        "title": title,
        "content": html_content,
        "visibility": "0",  # 비공개(임시저장)
    }

    try:
        response = requests.post(api_url, data=payload, timeout=30)
        res_json = response.json()
        
        status = res_json.get("tistory", {}).get("status")
        if status == "200":
            post_id = res_json.get("tistory", {}).get("postId")
            post_url = res_json.get("tistory", {}).get("url")
            msg = f"티스토리에 비공개(임시저장) 업로드 완료! (글 ID: {post_id}, URL: {post_url})"
            logger.info(msg)
            return {"success": True, "platform": "tistory", "id": post_id, "link": post_url, "message": msg}
        else:
            err_msg = res_json.get("tistory", {}).get("error_message", "알 수 없는 오류")
            logger.error(f"티스토리 API 오류: {err_msg}")
            return {"success": False, "platform": "tistory", "message": err_msg}
            
    except Exception as e:
        logger.error(f"티스토리 업로드 중 예외 발생: {e}", exc_info=True)
        return {"success": False, "platform": "tistory", "message": str(e)}


def publish_draft_post(title: str, html_content: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """
    설정된 블로그 플랫폼(워드프레스 또는 티스토리)에 맞춰
    '임시 저장(Draft)' 상태로 글을 업로드하는 통합 디스패처 함수입니다.
    """
    platform = config.BLOG_PLATFORM.lower()
    logger.info(f"선택된 블로그 플랫폼: [{platform}] - '임시 저장(Draft)' 모드로 업로드 진행")

    if platform == "both":
        wp_res = publish_to_wordpress(title=title, html_content=html_content, image_path=image_path)
        ts_res = publish_to_tistory(title=title, html_content=html_content)
        
        success = wp_res.get("success", False) or ts_res.get("success", False)
        
        msg = []
        if wp_res.get("success"):
            msg.append(f"WP 성공({wp_res.get('link')})")
        else:
            msg.append(f"WP 실패")
            
        if ts_res.get("success"):
            msg.append(f"티스토리 성공({ts_res.get('link')})")
        else:
            msg.append(f"티스토리 실패")
            
        return {
            "success": success,
            "platform": "both",
            "message": " | ".join(msg),
            "wp_result": wp_res,
            "ts_result": ts_res
        }
    elif platform == "tistory":
        return publish_to_tistory(title=title, html_content=html_content)
    else:
        # 기본값: WordPress
        return publish_to_wordpress(title=title, html_content=html_content, image_path=image_path)


def approve_and_publish_wordpress(post_id: str) -> bool:
    """
    임시저장(Draft)된 워드프레스 글을 공개 발행(Publish)으로 상태를 변경합니다.
    """
    wp_url = config.WORDPRESS_URL
    wp_user = config.WORDPRESS_USER
    wp_app_pwd = config.WORDPRESS_APP_PASSWORD

    if not wp_url or not wp_user or not wp_app_pwd:
        return False

    endpoints_to_try = [
        f"{wp_url}/wp-json/wp/v2/posts/{post_id}",
        f"{wp_url}/index.php?rest_route=/wp/v2/posts/{post_id}"
    ]
    payload = {"status": "publish"}

    try:
        response = None
        for endpoint in endpoints_to_try:
            response = requests.post(
                endpoint,
                json=payload,
                auth=HTTPBasicAuth(wp_user, wp_app_pwd),
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            if response.status_code != 404:
                break
                
        if response is not None and response.status_code in (200, 201):
            logger.info(f"워드프레스 글(ID: {post_id}) 발행(Publish) 성공!")
            return True
        else:
            status_code = response.status_code if response is not None else "Unknown"
            resp_text = response.text[:200] if response is not None else ""
            logger.error(f"워드프레스 발행 변경 실패 (HTTP {status_code}): {resp_text}")
            return False
    except Exception as e:
        logger.error(f"워드프레스 상태 변경 중 오류: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    test_title = f"[{datetime.date.today()}] 금융 시황 모닝 브리핑 (테스트)"
    test_content = "<h1>테스트 제목</h1><p>워드프레스/티스토리 임시 저장 테스트 본문입니다.</p>"
    result = publish_draft_post(test_title, test_content)
    print("\n--- 발행 결과 ---")
    print(result)

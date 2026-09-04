"""
설정 관리 모듈 (Configuration Module)
- .env 파일에서 환경변수 로드
- LLM 설정, 블로그 설정, 수집 키워드 기본값 관리
"""

import os
import sys
from dotenv import load_dotenv

# 콘솔 출력 UTF-8 인코딩 보정 (Windows 환경)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# .env 파일 로드
load_dotenv()

# ==========================================
# 1. AI LLM 설정
# ==========================================
# 기본 공급자: 'gemini' 또는 'openai'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# Google Gemini 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# OpenAI 설정 (선택 사항)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ==========================================
# 2. 블로그 발행 설정
# ==========================================
# 대상 플랫폼: 'wordpress', 'tistory', 또는 'both'
BLOG_PLATFORM = os.getenv("BLOG_PLATFORM", "both").lower()

# 워드프레스 REST API 설정
WORDPRESS_URL = os.getenv("WORDPRESS_URL", "").rstrip("/")
WORDPRESS_USER = os.getenv("WORDPRESS_USER", "")
# 주의: 워드프레스 관리자 -> 사용자 -> 프로필 하단의 '애플리케이션 비밀번호'를 사용해야 합니다.
WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD", "")
WORDPRESS_CATEGORY_ID = os.getenv("WORDPRESS_CATEGORY_ID", "")  # 카테고리 ID (선택)
# 발행 상태: 'draft' (임시저장 - 기본값) 또는 'publish' (즉시 공개 발행)
WORDPRESS_POST_STATUS = os.getenv("WORDPRESS_POST_STATUS", "draft").lower()

# 티스토리 API 설정 (선택 사항)
TISTORY_ACCESS_TOKEN = os.getenv("TISTORY_ACCESS_TOKEN", "")
TISTORY_BLOG_NAME = os.getenv("TISTORY_BLOG_NAME", "")

# ==========================================
# 3. 알림(Notification) 설정
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ==========================================
# 4. 데이터 수집 설정
# ==========================================
DEFAULT_KEYWORDS = [
    "국내 증시",
    "비트코인 시황",
    "나스닥",
    "유가",
    "코인",
    "금리",
    "채권"

]
MAX_ARTICLES_PER_KEYWORD = int(os.getenv("MAX_ARTICLES_PER_KEYWORD", "3"))


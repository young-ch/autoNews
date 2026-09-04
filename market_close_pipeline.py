"""
한국 증시 장마감 시황 파이프라인 (Market Close Pipeline)
- test.saemaul.or.kr:8888 서버에서 실시간 주도 테마, 거래대금 1000억 이상 주도주, 네이버 속보 뉴스 수집
- Gemini AI를 통한 전문적인 장마감 시황 분석 리포트(HTML) 생성
- 고해상도 장마감 전용 인포그래픽 썸네일 제작
- 워드프레스에 '임시 저장(Draft)' 상태로 자동 업로드
"""

import os
import sys
import json
import logging
import datetime
import requests
from typing import Dict, Any, List

import config
from processors import generate_with_gemini, clean_html_output
from publishers import publish_draft_post
import platform
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# 플랫폼별 한글 폰트 자동 감지 (Windows: 맑은 고딕 / Linux: 나눔고딕, Noto Sans)
if platform.system() == "Windows":
    plt.rc("font", family="Malgun Gothic")
else:
    plt.rc("font", family=["NanumGothic", "Noto Sans CJK KR", "DejaVu Sans"])
plt.rcParams["axes.unicode_minus"] = False


logger = logging.getLogger("MarketClosePipeline")

SAEMAUL_SERVER_URL = os.getenv("SAEMAUL_SERVER_URL", "http://test.saemaul.or.kr:8888")


def fetch_saemaul_market_data() -> Dict[str, Any]:
    """
    test.saemaul.or.kr 서버의 실시간 증시 API 엔드포인트에서
    주도 테마, 1000억 거래대금 종목, 네이버 뉴스를 수집합니다.
    """
    base_url = SAEMAUL_SERVER_URL.rstrip("/")
    logger.info(f"서버({base_url})로부터 한국 증시 실시간 테마 및 데이터 수집 시작...")

    result = {
        "top3_sectors": [],
        "all_sectors": [],
        "top_stocks_100b": [],
        "naver_news": []
    }

    # 1. 상위 3대 섹터
    try:
        r = requests.get(f"{base_url}/api/top3-sectors", timeout=6)
        if r.status_code == 200:
            result["top3_sectors"] = r.json().get("data", [])
            logger.info(f"상위 섹터 {len(result['top3_sectors'])}개 수집 완료")
    except Exception as e:
        logger.warning(f"상위 섹터 수집 실패: {e}")

    # 2. 전체 테마/업종 시세
    try:
        r = requests.get(f"{base_url}/api/sectors", timeout=6)
        if r.status_code == 200:
            result["all_sectors"] = r.json().get("data", [])
            logger.info(f"전체 테마 {len(result['all_sectors'])}개 수집 완료")
    except Exception as e:
        logger.warning(f"전체 테마 수집 실패: {e}")

    # 3. 거래대금 1000억 이상 주도주
    try:
        r = requests.get(f"{base_url}/api/100b-stocks", timeout=6)
        if r.status_code == 200:
            result["top_stocks_100b"] = r.json().get("data", [])
            logger.info(f"거래대금 1,000억+ 주도주 {len(result['top_stocks_100b'])}개 수집 완료")
    except Exception as e:
        logger.warning(f"1000억 주도주 수집 실패: {e}")

    # 4. 네이버 증권 최신 속보 뉴스
    try:
        r = requests.get(f"{base_url}/api/news", timeout=6)
        if r.status_code == 200:
            result["naver_news"] = r.json().get("data", [])
            logger.info(f"네이버 속보 뉴스 {len(result['naver_news'])}개 수집 완료")
    except Exception as e:
        logger.warning(f"네이버 뉴스 수집 실패: {e}")

    return result


def generate_market_close_thumbnail(today_str: str, strong_theme: str = "반도체 / AI") -> str:
    """
    장마감 전용 고해상도 인포그래픽 썸네일 이미지를 생성합니다.
    """
    output_dir = os.path.join(os.path.dirname(__file__), "charts")
    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, f"close_thumb_{today_str.replace('-', '')}.png")

    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor("#0f172a")  # 다크 슬레이트 블루

    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#0f172a")
    ax.set_xlim(0, 1200)
    ax.set_ylim(0, 630)
    ax.axis("off")

    # 상단 장마감 뱃지
    badge = patches.FancyBboxPatch(
        (60, 535), 180, 36,
        boxstyle="round,pad=0.2,rounding_size=8",
        facecolor="#dc2626", edgecolor="#f87171", linewidth=1.5
    )
    ax.add_patch(badge)
    ax.text(150, 553, "MARKET CLOSE", color="#ffffff", fontsize=12, fontweight="bold", ha="center", va="center")

    # 메인 타이틀
    ax.text(60, 480, "한국 증시 장마감 시황 & 주도 테마 총정리", color="#ffffff", fontsize=27, fontweight="bold")
    ax.text(60, 435, f"{today_str} | 오늘의 주도 테마 · 1000억 거래대금 집중주 · 핵심 속보", color="#94a3b8", fontsize=14)

    # 3대 분석 카드
    cards = [
        {
            "title": "[주도 테마 TOP]",
            "val": strong_theme,
            "sub": "상승률 상위 섹터 집중",
            "desc": "기관/외국인 동반 순매수 및\n테마 대장주 중심 급등세 연출",
            "accent": "#ef4444",
            "bg": "#1e293b"
        },
        {
            "title": "[거래대금 쏠림 현상]",
            "val": "1,000억+ 집중 수급",
            "sub": "SK하이닉스 등 주도주",
            "desc": "반도체·대형 IT 및 주도 섹터로\n시중 유동성 자금 강력 집중",
            "accent": "#3b82f6",
            "bg": "#1e293b"
        },
        {
            "title": "[시장 마감 분위기 & 체크]",
            "val": "차익실현 및 순환매",
            "sub": "내일장 관전 포인트",
            "desc": "장 후반 수급 공방 지속\n핵심 지지선 수급 유지 점검",
            "accent": "#10b981",
            "bg": "#1e293b"
        }
    ]


    cw = 340
    ch = 340
    spacing = 30
    sx = 60
    cy = 60

    for idx, c in enumerate(cards):
        x = sx + idx * (cw + spacing)
        card = patches.FancyBboxPatch(
            (x, cy), cw, ch,
            boxstyle="round,pad=0.2,rounding_size=12",
            facecolor=c["bg"], edgecolor="#334155", linewidth=1.5
        )
        ax.add_patch(card)

        # 타이틀
        ax.text(x + 20, cy + ch - 40, c["title"], color="#ffffff", fontsize=13, fontweight="bold")
        
        # 핵심 수치/테마
        ax.text(x + 20, cy + ch - 90, c["val"], color=c["accent"], fontsize=17, fontweight="bold")
        ax.text(x + 20, cy + ch - 120, c["sub"], color="#cbd5e1", fontsize=11)

        ax.plot([x + 20, x + cw - 20], [cy + ch - 145, cy + ch - 145], color="#334155", linewidth=1)

        ax.text(x + 20, cy + ch - 180, c["desc"], color="#94a3b8", fontsize=12, va="top", linespacing=1.6)

    # 하단 워터마크
    ax.text(1140, 25, "AI FINANCIAL REPORT | TEST.SAEMAUL.OR.KR", color="#475569", fontsize=9, ha="right")

    plt.savefig(image_path, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight", pad_inches=0)
    plt.close()
    return image_path


def build_market_close_prompt(data: Dict[str, Any]) -> str:
    """
    수집된 주도 테마, 1000억 종목, 네이버 뉴스를 바탕으로
    장마감 리포트 생성용 프롬프트를 구성합니다.
    """
    # 1. 상위 테마 정리
    top_sectors_txt = ""
    for s in data.get("top3_sectors", [])[:3]:
        s_name = s.get("sector_name", "")
        tot_amt = s.get("total_amount", 0) // 10000  # 조/억원 단위
        stocks_info = ", ".join([f"{st.get('name')}({st.get('change_rate')})" for st in s.get("stocks", [])[:4]])
        top_sectors_txt += f"- [{s_name}] 주요종목: {stocks_info}\n"

    # 전체 상위 테마 등락률
    sectors_rate_txt = ""
    for s in data.get("all_sectors", [])[:5]:
        s_name = s.get("name", "")
        rate = s.get("rate", "")
        stocks_sample = ", ".join([st.get("name") for st in s.get("stocks", [])[:3]])
        sectors_rate_txt += f"- {s_name} (+{rate}%): {stocks_sample}\n"

    # 2. 거래대금 1000억 이상 종목
    stocks_100b_txt = ""
    for st in data.get("top_stocks_100b", [])[:7]:
        name = st.get("name", "")
        code = st.get("code", "")
        chg = st.get("change_rate", "")
        amt = st.get("amount_str", "")
        theme = st.get("theme", "")
        stocks_100b_txt += f"- {name}({code}) | {chg} | 거래대금 {amt} | 테마: {theme}\n"

    # 3. 네이버 뉴스 3~5개 선별
    news_items = data.get("naver_news", [])[:5]
    news_txt = ""
    for idx, nw in enumerate(news_items, 1):
        news_txt += f"[{idx}] {nw.get('title')} ({nw.get('press')})\n    - 링크: {nw.get('link')}\n    - 요약: {nw.get('summary')}\n"

    system_instruction = """너는 여의도 금융투자업계의 15년 차 수석 증시 애널리스트야.
오늘 제공된 한국 거래소 실시간 장마감 데이터(주도 테마, 1000억 이상 대금 쏠림 종목, 네이버 뉴스)를 바탕으로,
개인 투자자들이 퇴근길에 읽고 내일장을 완벽하게 대비할 수 있는 최고급 장마감 시황 브리핑 리포트를 작성해 줘.

[작성 및 디자인 가이드라인 - 엄격 준수]
1. 제목은 <h1>[장마감 브리핑] 오늘 시장을 흔든 주도 테마 & 거래대금 쏠림 종목 총정리</h1> 형태로 작성.

2. 본문 서두에 📊 [오늘의 주도 테마 & 거래대금 스코어보드]:
   세련된 HTML <table>을 배치하여 (테마명 / 대표 상승 종목 / 등락률 / 수급 특징)을 한눈에 볼 수 있게 할 것.
   (스타일: table style="width:100%; border-collapse:collapse; margin:20px 0; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;")

3. 💡 [오늘 장 핵심 3줄 요약 박스]:
   <div style="background:#fef2f2; border-left:5px solid #ef4444; padding:16px 20px; border-radius:6px; margin:25px 0;">
   형태로 오늘 장의 핵심 흐름과 수급 특징을 3줄로 깔끔하게 요약할 것.

4. 3대 상세 분석 섹션 (<h2> 태그):
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">1. 오늘 가장 강했던 주도 테마 및 섹터 분석</h2>
     (상위 테마가 왜 올랐는지, 어떤 호재가 작용했는지 구체적 분석)
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">2. 거래대금 1,000억+ 쏠림 종목과 수급 특징</h2>
     (어떤 종목에 돈이 몰렸고, 외인/기관 수급과 차익실현 여부 분석)
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">3. 시장 전반적인 분위기 & 내일장 관전 포인트</h2>
     (순환매 가능성, 지지선 점검, 투자자 대응 전략)

5. 📰 [네이버 증권 핵심 뉴스 TOP 3~5선]:
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">4. 오늘 장 주요 네이버 증권 핵심 뉴스</h2>
   - 제공된 네이버 뉴스 데이터를 바탕으로, 각 기사마다 
     <p style="margin-bottom:12px;"><strong>• <a href="기사링크" target="_blank" style="color:#2563eb; text-decoration:none;">기사 제목</a></strong> <small style="color:#64748b;">(언론사)</small><br>기사 핵심 요약 내용</p>
     형태로 링크를 걸어 깔끔하게 3~5개를 보여줄 것.

6. 하단 면책조항:
   <div style="background:#f1f5f9; padding:15px; border-radius:6px; font-size:13px; color:#64748b; margin-top:40px;">
   <strong>⚠️ 투자 유의사항:</strong> 본 리포트는 시장 데이터 분석을 기반으로 작성된 참고 자료이며, 모든 투자의 최종 결정 및 책임은 투자자 본인에게 있습니다.
   </div>

7. 출력은 마크다운(```html) 없이 순수한 HTML 태그 문자열만 반환할 것."""

    user_content = f"""【오늘 장마감 실시간 거래소 데이터】

[1] 상위 테마 및 섹터 현황:
{top_sectors_txt}
[상위 상승 테마군]:
{sectors_rate_txt}

[2] 거래대금 1,000억원 이상 집중 종목:
{stocks_100b_txt}

[3] 네이버 금융 실시간 주요 속보 뉴스:
{news_txt}
"""
    return system_instruction, user_content


def run_market_close_pipeline():
    """장마감 파이프라인 전체 실행"""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    post_title = f"[{today_str}] 한국 증시 장마감 브리핑: 주도 테마 & 거래대금 쏠림 종목 총정리"

    print("=" * 70)
    print(f"🚀 장마감 시황 파이프라인 시작: {post_title}")
    print("=" * 70)

    # 1. test.saemaul.or.kr 데이터 수집
    data = fetch_saemaul_market_data()
    top_theme_name = "반도체 / AI"
    if data.get("top3_sectors"):
        top_theme_name = data["top3_sectors"][0].get("sector_name", "반도체")
    elif data.get("all_sectors"):
        top_theme_name = data["all_sectors"][0].get("name", "주도 테마")

    # 2. AI 리포트 생성 (Gemini)
    print("\n>>> [2단계] Gemini AI 장마감 전문 분석 리포트 생성 중...")
    sys_prompt, user_prompt = build_market_close_prompt(data)

    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=sys_prompt
    )

    response = model.generate_content(
        user_prompt,
        generation_config={"temperature": 0.3, "max_output_tokens": 8192}
    )

    html_content = clean_html_output(response.text)
    print(f"리포트 생성 완료 (글자 수: {len(html_content)}자)")

    # 3. 장마감 전용 썸네일 이미지 제작
    print("\n>>> [2.5단계] 장마감 인포그래픽 썸네일 이미지 생성 중...")
    thumb_path = generate_market_close_thumbnail(today_str, strong_theme=top_theme_name)
    print(f"썸네일 생성 완료: {thumb_path}")

    # 로컬 미리보기 저장
    preview_file = os.path.join(os.path.dirname(__file__), "last_market_close_report.html")
    with open(preview_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"로컬 미리보기 파일 저장 완료: {preview_file}")

    # 4. 워드프레스 임시 저장(Draft) 업로드
    print("\n>>> [3단계] 워드프레스 '임시 저장(Draft)' 상태 업로드 중...")
    result = publish_draft_post(
        title=post_title,
        html_content=html_content,
        image_path=thumb_path
    )
    print(f"결과: {result.get('message')}")
    print("=" * 70)
    print("🏁 장마감 파이프라인 완료!")
    print("=" * 70)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_market_close_pipeline()

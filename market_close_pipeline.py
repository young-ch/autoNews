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

SAEMAUL_SERVER_URL = os.getenv("SAEMAUL_SERVER_URL", "https://stock.marsticker.com")


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

    # 5. 오늘의 경제 캘린더 (당일 핵심 지표)
    result["economic_calendar"] = []
    try:
        r = requests.get(f"{base_url}/api/economic-calendar", timeout=6)
        if r.status_code == 200:
            cal_data = r.json().get("data", [])
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            # 오늘 일정 필터링
            today_events = [it for it in cal_data if it.get("date") == today_str]
            # 만약 오늘 일정이 적다면 중요도 높은 이번 주 일정으로 보충
            if len(today_events) < 3:
                today_events = [it for it in cal_data if it.get("importance", -1) >= 0][:8]
            else:
                # 중요도 높은 순 정렬
                today_events.sort(key=lambda x: x.get("importance", -1), reverse=True)
            result["economic_calendar"] = today_events
            logger.info(f"오늘의 경제 캘린더 일정 {len(today_events)}개 수집 완료")
    except Exception as e:
        logger.warning(f"경제 캘린더 수집 실패: {e}")

    return result


def generate_market_close_thumbnail(today_str: str, data: Dict[str, Any]) -> str:
    """
    실시간 수집 데이터를 바탕으로 고해상도(1200x630) 금융 대시보드 인포그래픽 썸네일을 생성합니다.
    - 좌측: 상승 주도 테마 TOP 3 및 거래대금
    - 우측 상단: 거래대금 1,000억+ 집중 수급주 TOP 4 (가로 바 게이지)
    - 우측 하단: 오늘 밤 주목할 글로벌 핵심 경제 캘린더 지표
    """
    output_dir = os.path.join(os.path.dirname(__file__), "charts")
    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, f"close_thumb_{today_str.replace('-', '')}.png")

    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor("#090d16")  # 딥 다크 네이비

    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#090d16")
    ax.set_xlim(0, 1200)
    ax.set_ylim(0, 630)
    ax.axis("off")

    # -------------------------------------------------------------
    # 1. 상단 헤더 영역
    # -------------------------------------------------------------
    # 장마감 뱃지
    badge_market = patches.FancyBboxPatch(
        (50, 565), 150, 32,
        boxstyle="round,pad=0.2,rounding_size=6",
        facecolor="#ef4444", edgecolor="none"
    )
    ax.add_patch(badge_market)
    ax.text(125, 581, "● MARKET CLOSE", color="#ffffff", fontsize=11, fontweight="bold", ha="center", va="center")

    # 날짜 뱃지
    badge_date = patches.FancyBboxPatch(
        (210, 565), 130, 32,
        boxstyle="round,pad=0.2,rounding_size=6",
        facecolor="#1e293b", edgecolor="#334155", linewidth=1
    )
    ax.add_patch(badge_date)
    ax.text(275, 581, today_str, color="#cbd5e1", fontsize=11, fontweight="bold", ha="center", va="center")

    # 메인 타이틀 & 서브 타이틀
    ax.text(50, 526, "한국 증시 장마감 브리핑 : 주도 테마 & 수급 집중주", color="#ffffff", fontsize=23, fontweight="bold")
    ax.text(50, 496, "실시간 주도 테마 TOP 3 · 거래대금 1,000억+ 쏠림 종목 · 글로벌 거시경제 캘린더 프리뷰", color="#94a3b8", fontsize=12)

    # -------------------------------------------------------------
    # 2. 좌측 패널: 실시간 상승 주도 테마 TOP 3 (x: 50, w: 530, h: 420)
    # -------------------------------------------------------------
    left_card = patches.FancyBboxPatch(
        (50, 50), 530, 425,
        boxstyle="round,pad=0.2,rounding_size=12",
        facecolor="#111827", edgecolor="#1f2937", linewidth=1.5
    )
    ax.add_patch(left_card)

    ax.text(75, 442, "● 실시간 상승 주도 테마 TOP 3", color="#f87171", fontsize=14, fontweight="bold")
    ax.plot([75, 555], [425, 425], color="#1f2937", linewidth=1)

    # 테마 데이터 추출
    top_sectors = data.get("top3_sectors", [])
    if not top_sectors and data.get("all_sectors"):
        for s in data.get("all_sectors", [])[:3]:
            top_sectors.append({
                "sector_name": s.get("name", "주도 테마"),
                "total_amount": 100000000,
                "stocks": s.get("stocks", [])
            })

    theme_colors = ["#f59e0b", "#10b981", "#06b6d4"]
    for i in range(3):
        ty = 305 - i * 115
        s_data = top_sectors[i] if i < len(top_sectors) else {}
        s_name = s_data.get("sector_name", f"주도 섹터 {i+1}")
        s_stocks = s_data.get("stocks", [])
        stocks_str = ", ".join([f"{st.get('name')}({st.get('change_rate')})" for st in s_stocks[:3]]) if s_stocks else "대형 주도주 수급 집중"

        # 테마 항목 배경 박스
        item_box = patches.FancyBboxPatch(
            (70, ty), 490, 100,
            boxstyle="round,pad=0.2,rounding_size=8",
            facecolor="#1a2234", edgecolor="#243048", linewidth=1
        )
        ax.add_patch(item_box)

        # 랭킹 뱃지
        rank_badge = patches.FancyBboxPatch(
            (85, ty + 60), 45, 26,
            boxstyle="round,pad=0.2,rounding_size=4",
            facecolor=theme_colors[i], edgecolor="none"
        )
        ax.add_patch(rank_badge)
        ax.text(107, ty + 73, f"#{i+1}", color="#ffffff", fontsize=11, fontweight="bold", ha="center", va="center")

        # 테마명
        display_name = s_name if len(s_name) <= 15 else s_name[:14] + "..."
        ax.text(142, ty + 73, display_name, color="#ffffff", fontsize=15, fontweight="bold", va="center")

        # 대표 종목
        ax.text(85, ty + 35, f"주요 종목 : {stocks_str}", color="#94a3b8", fontsize=11, va="center")

        # 거래대금/특징 태그
        tot_amt = s_data.get("total_amount", 0)
        amt_label = f"섹터 대금: 약 {tot_amt // 10000:,}억" if tot_amt > 0 else "기관·외인 순매수"
        ax.text(85, ty + 15, f"수급 특징 : {amt_label}", color="#38bdf8", fontsize=10, va="center")

    # -------------------------------------------------------------
    # 3. 우측 상단 패널: 거래대금 1,000억+ 집중 수급주 (x: 610, w: 540, h: 235)
    # -------------------------------------------------------------
    right_top_card = patches.FancyBboxPatch(
        (610, 240), 540, 235,
        boxstyle="round,pad=0.2,rounding_size=12",
        facecolor="#111827", edgecolor="#1f2937", linewidth=1.5
    )
    ax.add_patch(right_top_card)

    ax.text(635, 442, "● 거래대금 1,000억+ 집중 수급 주도주 (TOP 4)", color="#38bdf8", fontsize=13, fontweight="bold")
    ax.plot([635, 1125], [425, 425], color="#1f2937", linewidth=1)

    stocks_100b = data.get("top_stocks_100b", [])[:4]
    max_amount_val = 1
    for st in stocks_100b:
        amt_str = st.get("amount_str", "")
        val = 1000
        if "조" in amt_str:
            val = 10000
        elif "억" in amt_str:
            try:
                val = int(amt_str.replace("억", "").replace(",", "").strip())
            except Exception:
                val = 2000
        max_amount_val = max(max_amount_val, val)

    for idx, st in enumerate(stocks_100b):
        sy = 385 - idx * 45
        s_name = st.get("name", f"종목 {idx+1}")
        s_chg = st.get("change_rate", "0.0%")
        s_amt = st.get("amount_str", "1,000억+")
        is_plus = not s_chg.startswith("-")

        # 종목명
        ax.text(635, sy, s_name, color="#ffffff", fontsize=13, fontweight="bold", va="center")

        # 등락률
        chg_color = "#ef4444" if is_plus else "#3b82f6"
        ax.text(750, sy, s_chg, color=chg_color, fontsize=12, fontweight="bold", va="center")

        # 거래대금 막대 게이지 바
        bar_bg = patches.Rectangle((830, sy - 6), 170, 12, facecolor="#1e293b", edgecolor="none")
        ax.add_patch(bar_bg)

        # 게이지 채우기
        ratio = min(1.0, max(0.2, (4 - idx) / 4))
        bar_fill = patches.Rectangle((830, sy - 6), 170 * ratio, 12, facecolor="#2563eb", edgecolor="none")
        ax.add_patch(bar_fill)

        # 금액 표시
        ax.text(1015, sy, s_amt, color="#e2e8f0", fontsize=11, fontweight="bold", va="center")

    # -------------------------------------------------------------
    # 4. 우측 하단 패널: 오늘 밤 글로벌 경제 캘린더 (x: 610, w: 540, h: 175)
    # -------------------------------------------------------------
    right_bot_card = patches.FancyBboxPatch(
        (610, 50), 540, 175,
        boxstyle="round,pad=0.2,rounding_size=12",
        facecolor="#0f172a", edgecolor="#3b82f6", linewidth=1.5
    )
    ax.add_patch(right_bot_card)

    ax.text(635, 195, "● 오늘 밤 주목할 글로벌 핵심 경제 캘린더", color="#c084fc", fontsize=13, fontweight="bold")
    ax.plot([635, 1125], [178, 178], color="#1e293b", linewidth=1)

    cal_items = data.get("economic_calendar", [])
    important_events = [it for it in cal_items if it.get("importance", -1) >= 0]
    if not important_events:
        important_events = cal_items[:2]
    else:
        important_events = important_events[:2]

    for idx, ev in enumerate(important_events):
        ey = 145 - idx * 55
        country_code = ev.get("country", "US")
        country_tag = f"[{country_code}]"
        e_time = ev.get("time", "21:30")
        e_title = ev.get("title", "주요 경제 지표")
        if len(e_title) > 22:
            e_title = e_title[:21] + "..."
        imp_val = ev.get("importance", 0)
        stars_label = "HIGH ★★★" if imp_val > 0 else "MID ★★"
        e_forecast = ev.get("forecast", "-")
        e_prev = ev.get("previous", "-")

        # 시간 및 지표명
        ax.text(635, ey, f"{country_tag} {e_time} | {e_title}", color="#ffffff", fontsize=12, fontweight="bold", va="center")
        ax.text(1050, ey, stars_label, color="#fbbf24" if imp_val > 0 else "#94a3b8", fontsize=10, fontweight="bold", va="center")

        # 예상치 vs 이전치
        stat_text = f"예상치: {e_forecast}  |  직전치: {e_prev}"
        ax.text(635, ey - 22, stat_text, color="#94a3b8", fontsize=10, va="center")

    # 하단 워터마크
    ax.text(1150, 22, "SAEMAUL QUANT & THEME INTELLIGENCE | REAL-TIME REPORT", color="#475569", fontsize=9, ha="right")

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

    # 4. 오늘의 주요 글로벌 경제 캘린더 데이터 정리
    cal_items = data.get("economic_calendar", [])[:8]
    cal_txt = ""
    for c in cal_items:
        c_time = c.get("time", "")
        c_flag = c.get("flag", "")
        c_country = c.get("country_name", "")
        c_title = c.get("title", "")
        c_imp = c.get("importance_label", "보통")
        c_stars = c.get("impact_stars", "")
        c_fc = c.get("forecast", "-")
        c_prev = c.get("previous", "-")
        cal_txt += f"- [{c_time}] {c_flag} {c_country} | {c_title} | 중요도: {c_imp}({c_stars}) | 시장예상: {c_fc} | 이전치: {c_prev}\n"

    system_instruction = """너는 주식과 코인 투자에 푹 빠져있는 열정적인 개인 투자자야. 매일 퇴근 후 시장을 복기하며 개인 블로그에 '오늘의 장마감 일지'를 작성하는 콘셉트로 글을 써 줘.
오늘 제공된 한국 거래소 실시간 장마감 데이터(주도 테마, 1000억 이상 대금 쏠림 종목, 네이버 뉴스)와 [오늘의 글로벌 경제 캘린더 지표]를 바탕으로,
오늘 시장의 맥락과 오늘 밤/내일 장에 대한 나의 생각과 관점(View)을 친근하고 진지한 일지 말투(예: "~인 것 같다", "~라고 생각함", "~습니다")로 작성해 줘.
주의사항: "안녕하세요", "저는 투자자입니다" 같은 뻔한 인사말이나 서론은 다 빼고, 일지의 첫 줄처럼 바로 제목과 본론부터 시작해.

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
     (상위 테마가 왜 올랐는지, 어떤 호재/산업 모멘텀이 작용했는지 구체적 종목별 재료 분석)
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">2. 거래대금 1,000억+ 쏠림 종목과 외인·기관 수급 특징</h2>
     (어떤 종목에 유동성 자금이 몰렸고, 외인/기관의 매수/매도 특징과 차익실현 여부 심층 분석)
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">3. 시장 전반적인 분위기 & 내일장 관전 포인트</h2>
     (업종 순환매 가능성, 핵심 지지선 수급 유지 여부, 개인 투자자 실전 대응 전략)

5. 📅 [오늘 밤 & 내일 글로벌 핵심 경제 캘린더 프리뷰] (★ 매우 중요):
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">4. 오늘 밤 주목해야 할 글로벌 핵심 경제 지표 & 관전 포인트</h2>
   - 모바일 화면에서 표가 가로로 깨지지 않도록 반드시 `<div style="overflow-x: auto; width: 100%; font-size: 14px;">` 태그로 `<table>`을 감싸줄 것.
   - <table>의 각 컬럼 내용이 겹치지 않게 하되, 공간 절약을 위해 '중요도' 컬럼은 글자 대신 직관적인 아이콘(예: 🔴, 🟡)으로만 표시할 것. (중요도가 '낮음'인 지표는 표에서 제외)
   - 컬럼 구성: 발표 시간 / 국가 / 지표명 / 중요도 / 예상치 / 직전치 / 관전 포인트
   - 테이블 아래에 [개인 투자자 관점의 뷰(View) 코멘트]:
     - 오늘 밤 발표될 주요 경제 지표 결과가 내일 시장에 미칠 파급 효과에 대해, "내 생각엔 이러이러해서 이렇게 대응해야 할 것 같다"는 식으로 본인만의 시나리오와 관점을 일지처럼 친근하게 풀어쓸 것.

6. 📰 [네이버 증권 핵심 뉴스 TOP 3~5선]:
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">5. 오늘 장 주요 네이버 증권 핵심 뉴스</h2>
   - 제공된 네이버 뉴스 데이터를 바탕으로, 각 기사마다 
     <p style="margin-bottom:12px;"><strong>• <a href="기사링크" target="_blank" style="color:#2563eb; text-decoration:none;">기사 제목</a></strong> <small style="color:#64748b;">(언론사)</small><br>기사 핵심 요약 내용</p>
     형태로 링크를 걸어 깔끔하게 3~5개를 보여줄 것.

7. 하단 면책조항:
   <div style="background:#f1f5f9; padding:15px; border-radius:6px; font-size:13px; color:#64748b; margin-top:40px;">
   <strong>⚠️ 투자 유의사항:</strong> 본 리포트는 시장 데이터 분석을 기반으로 작성된 참고 자료이며, 모든 투자의 최종 결정 및 책임은 투자자 본인에게 있습니다.
   </div>

8. 출력은 마크다운(```html) 없이 순수한 HTML 태그 문자열만 반환할 것."""

    user_content = f"""【오늘 장마감 실시간 거래소 데이터】

[1] 상위 테마 및 섹터 현황:
{top_sectors_txt}
[상위 상승 테마군]:
{sectors_rate_txt}

[2] 거래대금 1,000억원 이상 집중 종목:
{stocks_100b_txt}

[3] 오늘 및 주간 글로벌 핵심 경제 캘린더:
{cal_txt if cal_txt else "오늘 예정된 주요 거시경제 지표 없음"}

[4] 네이버 금융 실시간 주요 속보 뉴스:
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

    # 1. test.saemaul.or.kr 데이터 수집 (테마, 1000억 종목, 뉴스, 경제 캘린더)
    data = fetch_saemaul_market_data()

    # 2. AI 리포트 생성 (Gemini)
    print("\n>>> [2단계] Gemini AI 장마감 전문 분석 리포트 생성 중 (경제 캘린더 포함)...")
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

    # 3. 장마감 전용 고해상도 인포그래픽 썸네일 이미지 제작
    print("\n>>> [2.5단계] 금융 대시보드 인포그래픽 썸네일 이미지 생성 중...")
    thumb_path = generate_market_close_thumbnail(today_str, data=data)
    print(f"썸네일 생성 완료: {thumb_path}")

    # 로컬 미리보기 저장
    preview_file = os.path.join(os.path.dirname(__file__), "last_market_close_report.html")
    with open(preview_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"로컬 미리보기 파일 저장 완료: {preview_file}")

    # 4. 워드프레스 업로드
    print("\n>>> [3단계] 워드프레스 업로드 중...")
    result = publish_draft_post(
        title=post_title,
        html_content=html_content,
        image_path=thumb_path
    )
    print(f"결과: {result.get('message')}")
    
    if result.get("success"):
        wp_post_id = result.get("wp_result", {}).get("id") or result.get("id")
        try:
            from notifiers import send_telegram_message
            msg = f"📝 <b>장마감 브리핑 초안 작성 완료!</b>\n\n결과: {result.get('message')}\n\n아래 버튼을 눌러 승인(발행)하거나, 편집기에 들어가서 광고를 삽입하고 직접 발행해주세요."
            send_telegram_message(msg, post_id=wp_post_id)
        except Exception as e:
            print(f"텔레그램 알림 발송 실패: {e}")
            
    print("=" * 70)
    print("🏁 장마감 파이프라인 완료!")
    print("=" * 70)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_market_close_pipeline()

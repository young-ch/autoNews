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
from processors import generate_with_gemini, generate_with_perplexity, clean_html_output
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

    system_instruction = """너는 대한민국 주식시장의 자금 흐름(Flow of Money)과 스마트머니의 수급을 날카롭게 추적하는 실전 금융 분석가이자 전문 투자 블로거야.
구글 검색엔진 및 애드센스 평가 로봇은 단순히 수치나 섹터 목록을 기계적으로 나열한 문서를 '가치 없는 단순 복사/저품질 문서'로 판단하여 거절합니다.
따라서 너는 제공된 한국 거래소 실시간 데이터(상승 테마, 거래대금 1,000억+ 집중 종목, 경제 캘린더, 네이버 뉴스)를 바탕으로,
오늘 시장을 주도한 테마의 자금 흐름과 특징, 스마트머니의 의도를 1,200~1,500자 내외의 구조화된 전문 리포트 형식으로 압축적이고 논리적으로 다듬어 작성해야 해.

[★ 매우 중요: 토큰 초과 방지 및 100% 완결성 원칙 - 엄격 준수]
- 글이 중간에 끊기지 않고 1번부터 5번 섹션까지 반드시 100% 완벽하게 끝까지 작성되어야 합니다.
- 각 분석 섹션(1, 2, 3번)은 장황한 사족을 빼고 핵심 1~2개 문단(200~250자 내외)으로 밀도 높고 군더더기 없이 서술하세요.
- 4번 경제 캘린더 표는 3~4개 주요 지표로 간결하게 표를 채우고, 5번 네이버 뉴스까지 반드시 끝까지 출력하세요.

말투는 딱딱한 기사체가 아니라, 시장의 맥락을 짚어주는 실전 투자자의 진지하면서도 친근한 블로그 일지 말투(예: "~인 것으로 분석된다", "~할 것으로 보인다", "~라고 판단함", "~습니다")를 일관되게 사용해 줘.
인사말이나 "안녕하세요" 같은 쓸데없는 서론은 일체 생략하고 바로 제목과 본론부터 시작해.

[구글 SEO 및 애드센스 승인 최적화 작성 가이드라인 - 엄격 준수]
1. 제목: <h1>[장마감 브리핑] 오늘 시장을 주도한 핵심 테마 자금 흐름 & 거래대금 쏠림 종목 심층 분석</h1>

2. 📊 [오늘의 주도 테마 & 자금 흐름 스코어보드]:
   - 상위 3~5개 테마를 세련된 HTML <table>로 깔끔하게 요약 (스타일: table style="width:100%; border-collapse:collapse; margin:20px 0; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;")
   - 컬럼: 주도 테마명 / 대표 상승 종목 / 등락률 / 수급 자금 흐름 특징

3. 💡 [오늘 장 핵심 요약 & 자금 이동 3줄 박스]:
   <div style="background:#fef2f2; border-left:5px solid #ef4444; padding:16px 20px; border-radius:6px; margin:25px 0;">
   형태로 오늘 시장 유동성이 어디서 빠져나와 어디로 이동했는지 3줄로 명확하게 요약할 것.

4. 3대 심층 논리 분석 섹션 (<h2> 태그 - 각 섹션마다 핵심 1~2문단씩 명확하게 서술):
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">1. 주도 테마 심층 분석: 자금 쏠림의 배경과 산업 모멘텀</h2>
     * 오늘 상위 테마군으로 막대한 유동성이 집중된 거시적 이유와 산업적 재료를 인과관계 중심으로 1~2문단(200자 내외)으로 압축 서술.
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">2. 거래대금 1,000억+ 집중 종목과 스마트머니 수급 특징</h2>
     * 1,000억 원 이상 유동성이 폭발한 상위 종목들의 수급 주체(외인/기관) 의도와 주가 지지력, 차익실현 여부를 1~2문단으로 명쾌하게 진단.
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">3. 시장 전반적인 수급 순환매 & 내일장 실전 대응 시나리오</h2>
     * 소외 섹터로의 순환매 가능성, 갭상승 시 뇌동매매 방지 팁과 실전 비중 관리 전략을 1~2문단으로 제시.

5. 📅 [오늘 밤 글로벌 핵심 경제 캘린더 & 시장 영향 프리뷰]:
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">4. 오늘 밤 주목해야 할 글로벌 경제 지표 & 환율·증시 파급 효과</h2>
   - 모바일 화면에서 표가 깨지지 않도록 반드시 `<div style="overflow-x:auto; width:100%; font-size:14px;">`로 감싸고,
   - 제공된 캘린더 데이터 중 핵심 3~4개를 선별하여 <table>(발표 시간 / 국가 / 지표명 / 중요도 / 예상치 / 직전치) 표를 반드시 끝까지 닫을 것(</table></div>).
   - 표 아래에 [전문가 시나리오]: 지표 결과가 내일 시초가와 환율에 미칠 영향을 1문단(150자 내외)으로 명쾌하게 서술.

6. 📰 [네이버 증권 핵심 뉴스 TOP 3선]:
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">5. 오늘 장 주요 네이버 증권 핵심 뉴스</h2>
   - 제공된 네이버 뉴스 데이터를 바탕으로 3개 기사를 선별하여:
     <p style="margin-bottom:12px;"><strong>• <a href="기사링크" target="_blank" style="color:#2563eb; text-decoration:none;">기사 제목</a></strong> <small style="color:#64748b;">(언론사)</small><br>기사 핵심 요약 내용 및 시장 시사점 1~2줄</p>
     형태로 링크를 걸어 깔끔하게 3개를 보여줄 것.

7. 하단 면책조항:
   <div style="background:#f1f5f9; padding:15px; border-radius:6px; font-size:13px; color:#64748b; margin-top:40px;">
   <strong>⚠️ 투자 유의사항:</strong> 본 리포트는 거래소 시장 데이터 및 자금 흐름 분석을 기반으로 작성된 독자적 분석 자료이며, 모든 투자의 최종 결정 및 책임은 투자자 본인에게 있습니다.
   </div>

8. 출력 규칙:
   - 마크다운(```html) 없이 순수한 HTML 태그 문자열만 반환할 것.
   - [1], [2], [11] 같은 검색 인라인 각주 번호는 본문 문장에 절대 삽입하지 말 것.
   - 모든 <table>, <div>, <tr>, <td>, <p> 태그는 완결되도록 정확히 닫을 것."""

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

    # 2. AI 리포트 생성 (Perplexity 우선, Gemini 자동 폴백)
    provider = getattr(config, "STOCK_LLM_PROVIDER", "perplexity").lower()
    print(f"\n>>> [2단계] AI 장마감 전문 분석 리포트 생성 중 (선택 공급자: {provider}, 경제 캘린더 포함)...")
    sys_prompt, user_prompt = build_market_close_prompt(data)

    html_content = ""
    if provider == "perplexity":
        try:
            html_content = generate_with_perplexity(user_prompt, sys_prompt=sys_prompt)
        except Exception as pplx_err:
            print(f"⚠️ Perplexity 분석 실패 ({pplx_err}) -> 안전 폴백(Gemini)으로 자동 전환합니다.")
            html_content = generate_with_gemini(user_prompt, sys_prompt=sys_prompt)
    elif provider == "openai":
        from processors import generate_with_openai
        html_content = generate_with_openai(user_prompt, sys_prompt=sys_prompt)
    else:
        html_content = generate_with_gemini(user_prompt, sys_prompt=sys_prompt)

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

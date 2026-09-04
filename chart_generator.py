"""
시황 차트 및 썸네일 생성 모듈 (Chart & Thumbnail Generator)
- matplotlib를 활용하여 블로그 대표 썸네일(1200x630) 자동 제작
- 코스피, 비트코인, 나스닥, 에너지 섹터 핵심 현황 인포그래픽 카드 렌더링
- 저작권 100% 안전한 고해상도 자체 제작 금융 인포그래픽 이미지
"""

import os
import datetime
import platform
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# 플랫폼별 한글 폰트 자동 감지 (Windows: 맑은 고딕 / Linux: 나눔고딕, Noto Sans)
if platform.system() == "Windows":
    plt.rc("font", family="Malgun Gothic")
else:
    # Linux 환경: fonts-nanum 패키지 기본 폰트
    plt.rc("font", family=["NanumGothic", "Noto Sans CJK KR", "DejaVu Sans"])
plt.rcParams["axes.unicode_minus"] = False


def generate_market_thumbnail(today_str: str = None) -> str:
    """
    전문 금융 분석 리포트용 고해상도 인포그래픽 썸네일 이미지를 자동 생성합니다.
    
    Returns:
        str: 생성된 이미지 파일의 절대 경로
    """
    if today_str is None:
        today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 저장 디렉토리 생성
    output_dir = os.path.join(os.path.dirname(__file__), "charts")
    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, f"market_thumb_{today_str.replace('-', '')}.png")

    # 1200x630 (16:9 비율, 블로그 및 SNS 썸네일 표준 규격)
    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor("#0b0f19")  # 세련된 딥 다크 네이비 배경

    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#0b0f19")
    ax.set_xlim(0, 1200)
    ax.set_ylim(0, 630)
    ax.axis("off")

    # 상단 헤더 배너 디자인
    # 상단 액센트 라인 (그라데이션 느낌의 네온 블루/퍼플)
    ax.plot([60, 1140], [600, 600], color="#3b82f6", linewidth=3, alpha=0.8)

    # 뱃지: DAILY BRIEFING
    badge_box = patches.FancyBboxPatch(
        (60, 540), 160, 34,
        boxstyle="round,pad=0.2,rounding_size=6",
        facecolor="#1e293b", edgecolor="#3b82f6", linewidth=1.5
    )
    ax.add_patch(badge_box)
    ax.text(140, 557, "MORNING BRIEF", color="#60a5fa", fontsize=11, fontweight="bold", ha="center", va="center")

    # 메인 타이틀
    ax.text(60, 495, "글로벌 금융 시황 모닝 브리핑", color="#ffffff", fontsize=26, fontweight="bold", ha="left")
    ax.text(60, 455, f"{today_str} | 국내증시 · 비트코인 · 나스닥 · 미국에너지 핵심 분석", color="#94a3b8", fontsize=13, ha="left")

    # 4대 핵심 섹터 카드 그리기
    cards_data = [
        {
            "title": "국내 증시 (KOSPI/KOSDAQ)",
            "status": "외인 순매수 반등",
            "desc": "기관/외국인 수급 개선 및\n대형 IT·반도체 기술적 반등",
            "tag": "단기 반등 모멘텀",
            "accent": "#10b981",  # 에메랄드 그린 (상승)
            "badge_bg": "#064e3b"
        },
        {
            "title": "가상자산 (Bitcoin/Crypto)",
            "status": "8만 달러선 공방",
            "desc": "금리 인하 기대감 유입\n현물 지지선 및 선물 변동성",
            "tag": "추세선 지지 확인",
            "accent": "#f59e0b",  # 골드 앰버
            "badge_bg": "#451a03"
        },
        {
            "title": "미국 증시 (NASDAQ)",
            "status": "금리 동결 시사 강세",
            "desc": "물가 지표 안정 및 빅테크 강세\n성장주 중심의 투자 심리 회복",
            "tag": "1.4%대 견조한 상승",
            "accent": "#3b82f6",  # 블루
            "badge_bg": "#1e3a8a"
        },
        {
            "title": "미국 에너지 (Energy/Oil)",
            "status": "셰브론 · 옥시덴탈",
            "desc": "지정학적 갈등에 따른 유가 반등\n버크셔 매수 종목 중심 관심",
            "tag": "배당 및 현금흐름 주목",
            "accent": "#ec4899",  # 로즈 핑크
            "badge_bg": "#831843"
        }
    ]

    card_width = 250
    card_height = 360
    card_spacing = 20
    start_x = 60
    card_y = 60

    for i, c in enumerate(cards_data):
        cx = start_x + i * (card_width + card_spacing)
        
        # 카드 배경 박스
        card = patches.FancyBboxPatch(
            (cx, card_y), card_width, card_height,
            boxstyle="round,pad=0.2,rounding_size=12",
            facecolor="#131b2e", edgecolor="#222f49", linewidth=1.5
        )
        ax.add_patch(card)

        # 상단 상태 뱃지
        tag_box = patches.FancyBboxPatch(
            (cx + 16, card_y + card_height - 45), card_width - 32, 28,
            boxstyle="round,pad=0.15,rounding_size=6",
            facecolor=c["badge_bg"], edgecolor=c["accent"], linewidth=1
        )
        ax.add_patch(tag_box)
        ax.text(cx + card_width / 2, card_y + card_height - 31, c["tag"], color=c["accent"], fontsize=10, fontweight="bold", ha="center", va="center")

        # 섹터 타이틀
        ax.text(cx + 16, card_y + card_height - 80, c["title"], color="#ffffff", fontsize=12.5, fontweight="bold", ha="left")

        # 액센트 상태 강조 텍스트
        ax.text(cx + 16, card_y + card_height - 115, c["status"], color=c["accent"], fontsize=14, fontweight="bold", ha="left")

        # 구분선
        ax.plot([cx + 16, cx + card_width - 16], [card_y + card_height - 135, card_y + card_height - 135], color="#222f49", linewidth=1)

        # 상세 내용
        ax.text(cx + 16, card_y + card_height - 180, c["desc"], color="#94a3b8", fontsize=10.5, ha="left", va="top", linespacing=1.6)

        # 미니 비주얼 데코레이션 (미니 트렌드 바)
        bar_y = card_y + 35
        bar_colors = ["#334155", "#334155", "#334155", c["accent"]]
        for bi, bc in enumerate(bar_colors):
            h = 10 + (bi + 1) * 7
            bar = patches.Rectangle((cx + 16 + bi * 14, bar_y), 9, h, facecolor=bc)
            ax.add_patch(bar)
            
        ax.text(cx + card_width - 16, bar_y + 10, "STABLE", color="#64748b", fontsize=9, fontweight="bold", ha="right")

    # 우측 하단 워터마크/출처 표기
    ax.text(1140, 25, "AI FINANCIAL INTELLIGENCE REPORT | STOCK-BLOG", color="#475569", fontsize=9, ha="right", va="center")

    plt.savefig(image_path, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight", pad_inches=0)
    plt.close()

    return image_path


if __name__ == "__main__":
    path = generate_market_thumbnail()
    print("생성된 차트 썸네일 경로:", path)

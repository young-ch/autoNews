"""
AI 추론부 (AI Processing Module)
- 수집된 기사 데이터를 금융 분석가 페르소나를 가진 LLM에 전달하여 시황 분석 리포트 생성
- google-generativeai (Gemini API) 및 OpenAI API 지원
- 블로그용 정제된 HTML 태그(<h1>, <h2>, <p>, <ul>, <li> 등) 출력
"""

import logging
import re
from typing import List, Dict, Any
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """너는 전문 금융 분석가야. 제공된 뉴스 데이터를 바탕으로 1) 국내 주식 단기/스윙 투자자의 관점, 2) 비트코인 현물 및 선물 방향성, 3) 미국 나스닥 및 에너지 섹터 동향을 중심으로 오늘 시장의 핵심 포인트를 3가지로 요약해 줘. 출력은 반드시 블로그 업로드용 HTML 태그(<h1>, <h2>, <p>, <ul>, <li>)를 사용해서 가독성 좋게 작성해."""


def clean_html_output(text: str) -> str:
    """
    LLM 응답에 포함될 수 있는 마크다운 코드 블록(```html ... ```)을 제거하고
    순수한 HTML 텍스트만 추출합니다.
    """
    text = text.strip()
    # ```html ... ``` 패턴 제거
    if text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def build_news_context(articles: List[Dict[str, Any]]) -> str:
    """
    수집된 뉴스 기사 목록을 프롬프트용 텍스트로 정리합니다.
    """
    if not articles:
        return "수집된 뉴스가 없습니다."

    lines = ["【수집된 최신 금융 뉴스 데이터】"]
    for idx, item in enumerate(articles, 1):
        lines.append(
            f"[{idx}] 분류: {item.get('keyword', '기타')}\n"
            f"  - 제목: {item.get('title', '')}\n"
            f"  - 일시: {item.get('published', '')}\n"
            f"  - 요약/스니펫: {item.get('summary', '')}\n"
            f"  - 링크: {item.get('link', '')}\n"
        )
    return "\n".join(lines)


def generate_with_gemini(prompt: str) -> str:
    """
    Google Generative AI (Gemini API)를 사용하여 HTML 리포트를 생성합니다.
    """
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")

    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    
    # 모델 인스턴스 생성 (system_instruction 지원)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT
    )

    logger.info(f"Gemini API ({config.GEMINI_MODEL}) 호출 중...")
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 3000,
        }
    )
    
    if not response.text:
        raise RuntimeError("Gemini로부터 비어있는 응답을 받았습니다.")
        
    return clean_html_output(response.text)


def generate_with_openai(prompt: str) -> str:
    """
    OpenAI API를 사용하여 HTML 리포트를 생성합니다.
    """
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("OpenAI 라이브러리가 설치되지 않았습니다. 'pip install openai'를 실행해 주세요.")

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    logger.info(f"OpenAI API ({config.OPENAI_MODEL}) 호출 중...")
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    content = response.choices[0].message.content
    return clean_html_output(content)


def generate_market_report(articles: List[Dict[str, Any]], economic_calendar: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    수집된 뉴스 기사와 경제 캘린더를 기반으로 AI 금융 분석 리포트(HTML 형식)를 생성합니다.
    
    Args:
        articles (List[Dict[str, Any]]): 수집된 뉴스 목록
        economic_calendar (Optional[List[Dict[str, Any]]]): 당일/주간 주요 글로벌 경제 지표 일정
        
    Returns:
        str: 블로그 업로드용 완성된 HTML 본문 문자열
    """
    if not articles:
        logger.warning("분석할 뉴스 기사가 없습니다. 기본 안내 문구를 반환합니다.")
        return "<h1>오늘의 시황 브리핑</h1><p>수집된 최신 뉴스 데이터가 없습니다.</p>"

    news_context = build_news_context(articles)

    cal_context = ""
    if economic_calendar:
        cal_context = "\n【오늘 및 주간 주요 글로벌 경제 캘린더 지표】\n"
        for c in economic_calendar[:7]:
            c_time = c.get("time", "")
            c_flag = c.get("flag", "")
            c_country = c.get("country_name", "")
            c_title = c.get("title", "")
            c_imp = c.get("importance_label", "보통")
            c_stars = c.get("impact_stars", "")
            c_fc = c.get("forecast", "-")
            c_prev = c.get("previous", "-")
            cal_context += f"- [{c_time}] {c_flag} {c_country} | {c_title} | 중요도: {c_imp}({c_stars}) | 시장예상: {c_fc} | 직전치: {c_prev}\n"

    calendar_instruction = ""
    if economic_calendar:
        calendar_instruction = """
5. 📅 [오늘의 주요 경제 캘린더 & 시장 영향 프리뷰]:
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">4. 오늘 하루 주목해야 할 글로벌 핵심 경제 발표 일정</h2>
   - 제공된 경제 캘린더 일정을 바탕으로 깔끔한 HTML <table>을 배치할 것 (발표시간 / 국가 / 지표명 / 중요도 / 예상치 / 직전치).
   - 테이블 하단에 애널리스트 관점에서 해당 지표가 오늘 시장(환율, 금리, 코스피/나스닥)에 미칠 관전 포인트를 2~3줄로 코멘트할 것.
"""

    user_prompt = f"""아래 제공된 최신 금융/증시 뉴스 데이터와 글로벌 경제 캘린더를 면밀히 분석하여 네이버 블로그나 워드프레스에 바로 게시할 수 있는 최고급 퀄리티의 시황 리포트를 작성해 주세요.

{news_context}
{cal_context}

[작성 및 디자인 가이드라인 - 엄격 준수]
1. 헤드라인:
   최상단에 눈길을 사로잡는 매력적인 <h1>오늘의 금융 모닝 브리핑: 주식·코인·글로벌 시황</h1> 작성.

2. 📊 [글로벌 마켓 핵심 스코어보드 (요약 테이블)]:
   본문 시작부에 방문자가 한눈에 시황을 파악할 수 있는 세련된 HTML <table>을 배치할 것.
   (스타일: table style="width:100%; border-collapse:collapse; margin:20px 0; background:#f8fafc; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;")
   - 컬럼: 자산군 / 핵심 동향 / 시장 상태(🟢반등, 🟡혼조, 🔴조정 등 이모지 활용)
   - 행: 1) 국내 증시, 2) 비트코인(가상자산), 3) 미국 나스닥, 4) 미국 에너지(유가/정유주)

3. 💡 [핵심 3줄 투자 전략 콜아웃 박스]:
   각 섹션 분석에 앞서 바쁜 현대인을 위한 <div style="background:#f0f7ff; border-left:5px solid #2563eb; padding:16px 20px; border-radius:6px; margin:25px 0;">
   형태의 핵심 3줄 결론 요약 박스를 배치할 것.

4. 3대 핵심 분석 섹션 (<h2> 태그 활용):
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">1. 국내 주식: 단기 및 스윙 투자 관점 포인트</h2>
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">2. 가상자산: 비트코인 현물 및 선물 방향성 분석</h2>
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">3. 글로벌 증시: 나스닥 & 미국 에너지(셰브론, 옥시덴탈) 동향</h2>
   각 섹션마다 <p style="line-height:1.8; color:#334155;"> 태그로 깊이 있는 해설과 <ul style="line-height:1.8;"><li> 핵심 불릿을 2~3개씩 포함할 것.
{calendar_instruction}
6. 하단 출처 및 면책조항 카드:
   - 글 말미에 참고 기사 링크 목록을 정리할 것.
   - <div style="background:#f1f5f9; padding:15px; border-radius:6px; font-size:13px; color:#64748b; margin-top:40px;">
     <strong>⚠️ 투자 유의사항:</strong> 본 리포트는 시장 뉴스 분석을 위한 참고 자료이며, 모든 투자의 최종 결정과 책임은 투자자 본인에게 있습니다.
     </div>

7. 응답은 마크다운 코드 블럭(```html) 없이 오직 완성된 순수 HTML 태그 문자열만 출력할 것.
"""

    provider = config.LLM_PROVIDER.lower()
    logger.info(f"AI 추론 엔진 가동 (선택된 공급자: {provider})")

    try:
        if provider == "openai":
            html_result = generate_with_openai(user_prompt)
        else:
            # 기본값: Gemini
            html_result = generate_with_gemini(user_prompt)
            
        logger.info(f"AI 리포트 생성 완료 (HTML 길이: {len(html_result)} 자)")
        return html_result

    except Exception as e:
        logger.error(f"AI 추론 중 오류 발생: {e}", exc_info=True)
        # 실패 시에도 파이프라인 중단을 방지하기 위한 최소 백업 HTML 생성
        fallback_html = f"""
        <h1>[시스템 임시 저장] 오늘의 금융 시황 뉴스 모음</h1>
        <p><strong>주의:</strong> AI 분석 리포트 생성 중 오류가 발생하여 수집된 기사 원문 목록을 임시 저장합니다. (오류 내용: {html_escape(str(e))})</p>
        <h2>수집된 최신 기사 목록</h2>
        <ul>
        """
        for a in articles:
            fallback_html += f"<li><strong>[{a.get('keyword')}]</strong> <a href='{a.get('link')}' target='_blank'>{a.get('title')}</a> ({a.get('published')})</li>"
        fallback_html += "</ul>"
        return fallback_html.strip()


def html_escape(text: str) -> str:
    """간단한 HTML 이스케이프 유틸리티"""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sample_articles = [
        {"keyword": "국내 증시", "title": "코스피 1.7% 반등 마감", "published": "2026-09-03", "summary": "외국인 순매수 유입", "link": "https://example.com/1"},
        {"keyword": "비트코인 시황", "title": "비트코인 8만 달러 회복 시도", "published": "2026-09-03", "summary": "금리 인하 기대감에 가상자산 반등", "link": "https://example.com/2"}
    ]
    report = generate_market_report(sample_articles)
    print("\n--- 생성된 HTML 결과 요약 ---\n")
    print(report[:500] + "...")

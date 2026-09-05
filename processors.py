"""
AI 추론부 (AI Processing Module)
- 수집된 기사 데이터를 금융 분석가 페르소나를 가진 LLM에 전달하여 시황 분석 리포트 생성
- google-generativeai (Gemini API) 및 OpenAI API 지원
- 블로그용 정제된 HTML 태그(<h1>, <h2>, <p>, <ul>, <li> 등) 출력
"""

import logging
import re
from typing import List, Dict, Any, Optional
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """너는 주식과 코인 투자에 푹 빠져있는 열정적인 개인 투자자야. 매일 퇴근 후 시장을 복기하며 개인 블로그에 '오늘의 투자 일지'를 작성하는 콘셉트로 글을 써 줘.
제공된 뉴스 데이터를 바탕으로 1) 국내 주식 단기/스윙 관점에서의 생각, 2) 비트코인 현물/선물 방향성에 대한 고민, 3) 미국 나스닥 및 에너지 섹터 동향에 대한 사견을 중심으로 오늘 시장의 핵심 포인트를 3가지로 요약해 줘.
특히 주요 이슈나 경제 지표를 언급할 때는 단순히 기사 내용만 나열하지 말고, "내 관점(View)에서는 이러이러해서 앞으로 이렇게 흘러갈 것 같다"라는 식으로 본인만의 해석을 설명하듯이 덧붙여 줘.
딱딱한 전문가나 뉴스 기사 말투가 아니라, 친근하면서도 진지하게 분석하는 개인 투자자의 블로그 포스팅 말투(예: "~인 것 같다", "~해 보임", "~라고 생각함", "~습니다")를 사용해 줘.
출력은 반드시 블로그 업로드용 HTML 태그(<h1>, <h2>, <p>, <ul>, <li>)를 사용해서 가독성 좋게 작성해.
주의사항: "안녕하세요", "저는 투자자입니다" 같은 뻔한 인사말이나 서론은 다 빼고, 개인 일지의 첫 줄처럼 바로 제목과 본론부터 시작해."""


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


def generate_with_gemini(prompt: str, sys_prompt: str = SYSTEM_PROMPT) -> str:
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
        system_instruction=sys_prompt
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


def generate_with_gemini_vision(prompt: str, image_path: str, sys_prompt: str = SYSTEM_PROMPT) -> str:
    """
    Google Generative AI (Gemini API)를 사용하여 이미지와 텍스트를 함께 전송해 HTML 리포트를 생성합니다.
    """
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    import google.generativeai as genai
    import PIL.Image
    import os

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    genai.configure(api_key=config.GEMINI_API_KEY)
    
    # Vision 모델(gemini-1.5-flash 등) 인스턴스 생성
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=sys_prompt
    )

    logger.info(f"Gemini Vision API ({config.GEMINI_MODEL}) 호출 중...")
    
    img = PIL.Image.open(image_path)
    
    response = model.generate_content(
        [prompt, img],
        generation_config={
            "temperature": 0.5,
            "max_output_tokens": 3000,
        }
    )
    
    if not response.text:
        raise RuntimeError("Gemini로부터 비어있는 응답을 받았습니다.")
        
    return clean_html_output(response.text)


def generate_with_openai(prompt: str, sys_prompt: str = SYSTEM_PROMPT) -> str:
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
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    content = response.choices[0].message.content
    return clean_html_output(content)


def generate_daily_life_post(image_path: str, user_caption: str) -> str:
    """
    업로드된 사진과 사장님의 짧은 코멘트를 기반으로 '나의 일상/육아' 블로그 포스팅 초안을 생성합니다.
    """
    user_prompt = f"""첨부된 사진과 아래의 짤막한 메모를 보고, 개인 블로그(일상/육아)에 어울리는 포스팅 초안을 작성해 주세요.

[사장님의 메모]: {user_caption if user_caption else '(메모 없음)'}

[작성 및 디자인 가이드라인]
1. 사진의 분위기와 메모의 의도를 살려, 친근하고 따뜻한 블로거 말투(~했어요, ~입니다)로 자연스럽게 이야기를 풀어주세요.
2. 억지스러운 서론 없이 바로 사진에 대한 이야기로 들어갈 것.
3. 글 하단에는 블로그 주인이 최종적으로 자신의 진짜 느낀점이나 결론을 덧붙일 수 있도록 아래와 같은 문구를 눈에 띄게 배치할 것:
   <div style="background:#fffbeb; border:2px dashed #f59e0b; padding:20px; margin:25px 0; color:#b45309; font-weight:bold; text-align:center; border-radius:8px;">
   [사장님의 찐후기 또는 추가하고 싶은 내용을 자유롭게 적어주세요!]
   </div>
4. 모든 HTML 태그(<div>, <p> 등)는 짝을 맞춰 정확하게 닫을 것 (화면 깨짐 방지).
5. 마크다운(```html) 기호 없이 순수 HTML만 출력할 것.
"""
    sys_prompt = "너는 따뜻하고 유쾌한 글솜씨를 가진 파워 블로거야. 주어진 사진을 보고 사람들의 공감을 이끌어낼 수 있는 일상/육아 포스팅을 멋지게 작성해 줘."
    
    try:
        return generate_with_gemini_vision(user_prompt, image_path, sys_prompt=sys_prompt)
    except Exception as e:
        logger.error(f"일상 포스트 생성 중 오류: {e}")
        return f"<h1>[시스템 임시 저장] 오류 발생</h1><p>{str(e)}</p>"

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
   - 모바일 화면에서 표가 깨지지 않도록 반드시 `<div style="overflow-x: auto; width: 100%;">` 태그로 `<table>`을 감싸줄 것.
   - 공간 절약을 위해 '중요도' 컬럼은 🔴, 🟡 같은 직관적인 아이콘으로만 표시할 것.
   - 컬럼 구성: 발표 시간 / 국가 / 지표명 / 중요도 / 예상치 / 직전치
   - 테이블 하단에 일반 개인 투자자 관점에서 해당 지표가 오늘 내 계좌(코스피/나스닥 등)에 미칠 영향을 "내 생각엔 이럴 것 같다"는 뉘앙스로 2~3줄 코멘트할 것.
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


def generate_us_market_report(articles: List[Dict[str, Any]], us_sectors: List[Dict[str, Any]], us_macro: Dict[str, Any], economic_calendar: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    미국 11대 섹터, 미국채 장단기, 원유 가격, 최신 미국 뉴스를 종합하여
    국장(한국 시장)에 대한 뷰를 제시하는 시황 리포트를 생성합니다.
    """
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
            c_fc = c.get("forecast", "-")
            c_prev = c.get("previous", "-")
            cal_context += f"- [{c_time}] {c_flag} {c_country} | {c_title} | 중요도: {c_imp} | 시장예상: {c_fc} | 직전치: {c_prev}\n"

    sector_context = "\n【미국 11대 섹터 시세 흐름】\n"
    for s in us_sectors:
        sector_context += f"- {s.get('icon', '')} {s.get('kr_name', s.get('name'))}: {s.get('avg_rate_str', '0%')}\n"

    macro_context = "\n【미국 거시 지표 (국채/유가)】\n"
    for k, v in us_macro.items():
        macro_context += f"- {k}: {v.get('price')} (변동: {v.get('change_pct')}%) \n"

    user_prompt = f"""아래 제공된 최신 미국 시장 데이터(섹터, 거시지표, 뉴스)와 경제 캘린더를 면밀히 분석하여 네이버 블로그나 워드프레스에 바로 게시할 수 있는 최고급 퀄리티의 아침 시황 리포트를 작성해 주세요.

{news_context}
{macro_context}
{sector_context}
{cal_context}

[작성 및 디자인 가이드라인 - 엄격 준수]
1. 헤드라인:
   최상단에 눈길을 사로잡는 매력적인 <h1>오늘의 증시 모닝 브리핑: 미 증시 기반 국장 뷰</h1> 작성.

2. 📊 [간밤의 미 증시 & 매크로 요약 테이블]:
   미국 섹터별 흐름과 국채 금리, 원유 가격을 한눈에 볼 수 있는 세련된 HTML <table>을 배치할 것.
   (스타일: table style="width:100%; border-collapse:collapse; margin:20px 0; background:#f8fafc; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;")
   - 컬럼: 지표/섹터 / 수치 및 등락 / 시장 상태(🟢반등, 🔴조정 등 이모지 활용)

3. 💡 [나의 국장 뷰 (핵심 3줄 요약 박스)]:
   분석에 앞서 오늘 한국 시장(국장)이 어떻게 흘러갈지 예측하는 핵심 3줄 결론 요약 박스를 배치할 것.
   <div style="background:#f0f7ff; border-left:5px solid #2563eb; padding:16px 20px; border-radius:6px; margin:25px 0;">

4. 3대 핵심 분석 섹션 (<h2> 태그 활용):
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">1. 매크로 지표 분석 (미국채 & 원유)</h2>
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">2. 미국 섹터별 흐름 및 특징주 동향</h2>
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">3. 오늘 국장(한국 시장) 투자 전략 및 관점</h2> (가장 중요: 앞선 데이터를 종합하여 오늘 코스피/코스닥 방향성과 유망 섹터를 본인만의 시각으로 설명)
   각 섹션마다 <p style="line-height:1.8; color:#334155;"> 태그로 깊이 있는 해설과 <ul style="line-height:1.8;"><li> 핵심 불릿을 포함할 것.

5. 📅 [오늘의 주요 경제 캘린더] (데이터가 있을 경우 표로 정리)

6. 하단 출처 및 면책조항 카드:
   - <div style="background:#f1f5f9; padding:15px; border-radius:6px; font-size:13px; color:#64748b; margin-top:40px;">
     <strong>⚠️ 투자 유의사항:</strong> 본 리포트는 시장 뉴스 분석을 위한 참고 자료이며, 모든 투자의 최종 결정과 책임은 투자자 본인에게 있습니다.
     </div>

7. 응답은 마크다운 코드 블럭(```html) 없이 오직 완성된 순수 HTML 태그 문자열만 출력할 것.
"""

    provider = config.LLM_PROVIDER.lower()
    logger.info(f"AI 추론 엔진 가동 (선택된 공급자: {provider})")

    morning_sys_prompt = """너는 글로벌 매크로 지표(채권, 원유)와 미국 증시 섹터 흐름을 면밀히 분석하여, 오늘 한국 주식시장(코스피/코스닥)의 개장 전 방향성과 유망 섹터를 족집게처럼 짚어주는 실전 투자 전문가야.
개인 블로그에 '오늘의 아침 시황 뷰'를 작성하는 콘셉트로 친근하게 글을 써 줘.
"내 생각엔 오늘 국장은 어떨 것 같다", "이런 섹터가 좋아 보임" 같이 본인만의 관점(View)을 명확히 제시해야 해.
주의사항: "안녕하세요", "저는 전문가입니다" 같은 서론은 모두 빼고, 제공된 데이터 기반의 통찰력 있는 본론만 바로 출력해.
출력은 블로그 업로드용 HTML 태그(<h1>, <h2>, <p>, <ul>, <li>, <table> 등)만 사용해."""

    try:
        if provider == "openai":
            html_result = generate_with_openai(user_prompt, sys_prompt=morning_sys_prompt)
        else:
            html_result = generate_with_gemini(user_prompt, sys_prompt=morning_sys_prompt)
            
        logger.info(f"AI 리포트 생성 완료 (HTML 길이: {len(html_result)} 자)")
        return html_result

    except Exception as e:
        logger.error(f"AI 추론 중 오류 발생: {e}", exc_info=True)
        return "<h1>[시스템 임시 저장] 오류 발생</h1>"


def html_escape(text: str) -> str:
    """간단한 HTML 이스케이프 유틸리티"""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )

def generate_trend_report(articles: List[Dict[str, Any]]) -> str:
    """
    일상/육아 관련 뉴스를 분석하여 트렌드 초안 리포트를 생성합니다.
    """
    news_context = build_news_context(articles)
    
    user_prompt = f"""아래 제공된 최신 육아/일상 트렌드 기사 데이터를 분석하여 네이버 블로그나 워드프레스에 게시할 초안을 작성해 주세요.

{news_context}

[작성 및 디자인 가이드라인]
1. 헤드라인: 최상단에 눈길을 끄는 <h1>이번 주 알아두면 쓸데있는 육아 & 일상 트렌드 TOP 3</h1> 추가.
2. 기사 내용 중 가장 주목할만한 아이템이나 이슈 3가지를 골라 소개할 것 (<h2> 태그 사용).
3. 각 주제마다 친근한 블로거 말투로 요약해주고, 블로그 주인이 직접 자신의 경험이나 후기를 채워넣을 수 있도록 아래와 같은 문구를 눈에 띄게 배치할 것:
   <div style="background:#fffbeb; border:2px dashed #f59e0b; padding:20px; margin:25px 0; color:#b45309; font-weight:bold; text-align:center; border-radius:8px;">
   [이곳에 사장님의 실제 경험, 구매 후기, 또는 쿠팡 파트너스 링크를 작성해주세요!]
   </div>
4. 뻔한 서론 없이 바로 본론으로 들어갈 것. 모든 HTML 태그는 닫는 태그(</div>, </p> 등)를 완벽하게 작성해서 화면 깨짐을 방지할 것.
5. 마크다운(```html) 없이 순수 HTML만 출력할 것.
"""

    sys_prompt = "너는 요즘 뜨는 핫템과 육아 정보를 누구보다 빠르게 캐치하는 센스있는 블로거야. 독자들에게 유용한 정보를 전달하면서도, 글쓴이가 직접 자신의 경험을 추가할 수 있는 여백을 남겨주는 초안 작성기 역할을 해 줘."
    
    provider = config.LLM_PROVIDER.lower()
    try:
        if provider == "openai":
            return generate_with_openai(user_prompt, sys_prompt=sys_prompt)
        return generate_with_gemini(user_prompt, sys_prompt=sys_prompt)
    except Exception as e:
        logger.error(f"트렌드 리포트 생성 중 오류: {e}")
        return "<h1>[시스템 임시 저장] 오류 발생</h1>"

def generate_weekly_market_report(articles: List[Dict[str, Any]], us_sectors: List[Dict[str, Any]], us_macro: Dict[str, Any], economic_calendar: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    한 주간의 시장 흐름과 다음 주 일정을 요약하는 주말 시황 리포트를 생성합니다.
    """
    news_context = build_news_context(articles)
    
    cal_context = ""
    if economic_calendar:
        cal_context = "\n【다음 주 글로벌 경제 캘린더 프리뷰】\n"
        for c in economic_calendar[:10]:
            cal_context += f"- [{c.get('date', '')} {c.get('time', '')}] {c.get('country_name', '')} {c.get('title', '')} | 중요도: {c.get('importance_label', '보통')}\n"

    sector_context = "\n【이번 주 미국 11대 섹터 요약】\n"
    for s in us_sectors:
        sector_context += f"- {s.get('kr_name', s.get('name'))}: 현재 흐름 {s.get('avg_rate_str', '0%')}\n"

    macro_context = "\n【현재 매크로 지표】\n"
    for k, v in us_macro.items():
        macro_context += f"- {k}: {v.get('price')} (변동: {v.get('change_pct')}%) \n"

    user_prompt = f"""아래 데이터를 분석하여 주말용 '주간 시황 총정리' 블로그 초안을 작성해 주세요.

{news_context}
{macro_context}
{sector_context}
{cal_context}

[작성 및 디자인 가이드라인]
1. 헤드라인: 최상단에 <h1>[주말 결산] 이번 주 증시 요약 & 다음 주 핵심 체크포인트</h1> 추가.
2. 이번 주 주요 이슈 요약과 다음 주 경제 캘린더를 <table>로 깔끔하게 정리할 것.
   - 표 스타일 필수 적용: <table style="width:100%; border-collapse:collapse; margin:20px 0; border:1px solid #e2e8f0; font-size:15px;">
   - <th> (제목 행) 스타일: <th style="background:#f1f5f9; padding:12px; border:1px solid #e2e8f0; text-align:center;">
   - <td> (내용 행) 스타일: <td style="padding:12px; border:1px solid #e2e8f0;">
3. 글 하단에 블로그 주인이 자신의 주간 인사이트를 적을 수 있도록 넓은 영역을 만들어 줄 것:
   <div style="background:#f0f9ff; border-top:4px solid #0ea5e9; padding:25px; margin-top:40px; border-radius:4px;">
   <h2 style="color:#0369a1; margin-top:0;">💡 나의 주간 생각 및 다음 주 대응 전략</h2>
   <p style="color:#0284c7; line-height:1.6;">[주말 동안 정리하신 사장님의 투자 시나리오, 눈여겨볼 종목, 멘탈 관리 팁 등을 이곳에 자유롭게 작성해주세요.]</p>
   </div>
4. 모든 HTML 태그(<table>, <div>, <tr>, <td> 등)는 짝을 맞춰 정확하게 닫을 것 (화면 깨짐 방지).
5. 마크다운(```html) 기호 없이 순수 HTML만 출력할 것.
"""
    sys_prompt = "너는 글로벌 매크로와 주식 시장을 거시적 관점에서 분석하는 주말 시황 전문가야. 독자들이 한 주를 돌아보고 다음 주를 대비할 수 있도록 데이터를 객관적으로 정리해 줘."
    
    provider = config.LLM_PROVIDER.lower()
    try:
        if provider == "openai":
            return generate_with_openai(user_prompt, sys_prompt=sys_prompt)
        return generate_with_gemini(user_prompt, sys_prompt=sys_prompt)
    except Exception as e:
        logger.error(f"주간 리포트 생성 중 오류: {e}")
        return "<h1>[시스템 임시 저장] 오류 발생</h1>"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sample_articles = [
        {"keyword": "국내 증시", "title": "코스피 1.7% 반등 마감", "published": "2026-09-03", "summary": "외국인 순매수 유입", "link": "https://example.com/1"},
    ]
    report = generate_market_report(sample_articles)
    print("\n--- 생성된 HTML 결과 요약 ---\n")
    print(report[:500] + "...")

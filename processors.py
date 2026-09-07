"""
AI 추론부 (AI Processing Module)
- 수집된 기사 데이터를 금융 분석가 페르소나를 가진 LLM에 전달하여 시황 분석 리포트 생성
- google-generativeai (Gemini API) 및 OpenAI API 지원
- 블로그용 정제된 HTML 태그(<h1>, <h2>, <p>, <ul>, <li> 등) 출력
"""

import logging
import re
from typing import List, Dict, Any, Optional, Union
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """너는 주식과 코인 투자에 푹 빠져있는 열정적인 개인 투자자야. 매일 퇴근 후 시장을 복기하며 개인 블로그에 '오늘의 투자 일지'를 작성하는 콘셉트로 글을 써 줘.
제공된 뉴스 데이터를 바탕으로 1) 국내 주식 단기/스윙 관점에서의 생각, 2) 비트코인 현물/선물 방향성에 대한 고민, 3) 미국 나스닥 및 에너지 섹터 동향에 대한 사견을 중심으로 오늘 시장의 핵심 포인트를 3가지로 요약해 줘.
특히 주요 이슈나 경제 지표를 언급할 때는 단순히 기사 내용만 나열하지 말고, "내 관점(View)에서는 이러이러해서 앞으로 이렇게 흘러갈 것 같다"라는 식으로 본인만의 해석을 설명하듯이 덧붙여 줘.
딱딱한 전문가나 뉴스 기사 말투가 아니라, 친근하면서도 진지하게 분석하는 개인 투자자의 블로그 포스팅 말투(예: "~인 것 같다", "~해 보임", "~라고 생각함", "~습니다")를 사용해 줘.
출력은 반드시 블로그 업로드용 HTML 태그(<h1>, <h2>, <p>, <ul>, <li>)를 사용해서 가독성 좋게 작성해.
주의사항: "안녕하세요", "저는 투자자입니다" 같은 뻔한 인사말이나 서론은 다 빼고, 개인 일지의 첫 줄처럼 바로 제목과 본론부터 시작해."""


def fix_unclosed_html_tags(html: str) -> str:
    """
    LLM이 생성한 HTML에서 닫히지 않은 테이블 및 블록 태그를 안전하게 닫아줍니다.
    """
    # 닫히지 않은 td/th 닫기
    open_td = len(re.findall(r'<td[\s>]', html, re.IGNORECASE))
    close_td = len(re.findall(r'</td>', html, re.IGNORECASE))
    if open_td > close_td:
        html += "</td>" * (open_td - close_td)

    open_th = len(re.findall(r'<th[\s>]', html, re.IGNORECASE))
    close_th = len(re.findall(r'</th>', html, re.IGNORECASE))
    if open_th > close_th:
        html += "</th>" * (open_th - close_th)

    # 닫히지 않은 tr 닫기
    open_tr = len(re.findall(r'<tr[\s>]', html, re.IGNORECASE))
    close_tr = len(re.findall(r'</tr>', html, re.IGNORECASE))
    if open_tr > close_tr:
        html += "</tr>" * (open_tr - close_tr)

    # 닫히지 않은 tbody 닫기
    open_tbody = len(re.findall(r'<tbody[\s>]', html, re.IGNORECASE))
    close_tbody = len(re.findall(r'</tbody>', html, re.IGNORECASE))
    if open_tbody > close_tbody:
        html += "</tbody>" * (open_tbody - close_tbody)

    # 닫히지 않은 thead 닫기
    open_thead = len(re.findall(r'<thead[\s>]', html, re.IGNORECASE))
    close_thead = len(re.findall(r'</thead>', html, re.IGNORECASE))
    if open_thead > close_thead:
        html += "</thead>" * (open_thead - close_thead)

    # 닫히지 않은 table 닫기
    open_table = len(re.findall(r'<table[\s>]', html, re.IGNORECASE))
    close_table = len(re.findall(r'</table>', html, re.IGNORECASE))
    if open_table > close_table:
        html += "</table>" * (open_table - close_table)

    # 닫히지 않은 ul/ol 닫기
    open_ul = len(re.findall(r'<ul[\s>]', html, re.IGNORECASE))
    close_ul = len(re.findall(r'</ul>', html, re.IGNORECASE))
    if open_ul > close_ul:
        html += "</ul>" * (open_ul - close_ul)

    open_ol = len(re.findall(r'<ol[\s>]', html, re.IGNORECASE))
    close_ol = len(re.findall(r'</ol>', html, re.IGNORECASE))
    if open_ol > close_ol:
        html += "</ol>" * (open_ol - close_ol)

    # 닫히지 않은 div 닫기
    open_div = len(re.findall(r'<div[\s>]', html, re.IGNORECASE))
    close_div = len(re.findall(r'</div>', html, re.IGNORECASE))
    if open_div > close_div:
        html += "</div>" * (open_div - close_div)

    return html


def clean_html_output(text: str) -> str:
    """
    LLM 응답에 포함될 수 있는 마크다운 코드 블록(```html ... ```) 및
    Perplexity 인라인 검색 각주 번호([1], [11], [12] 등)를 제거하고
    닫히지 않은 HTML 태그를 자동 보정합니다.
    """
    text = text.strip()
    # ```html ... ``` 패턴 제거
    if text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    # Perplexity 인라인 검색 출처 각주 번호 제거 (예: [1], [11], [12] 등)
    text = re.sub(r'\[\d+\]', '', text)
    
    # 닫히지 않은 HTML 태그 자동 보정
    text = fix_unclosed_html_tags(text)
    
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


def generate_with_openai(prompt: str, sys_prompt: str = SYSTEM_PROMPT) -> str:
    """
    OpenAI REST API를 직접 호출하여 HTML 리포트를 생성합니다.
    """
    import requests as req

    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY.strip()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config.OPENAI_MODEL or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 3000
    }

    logger.info(f"OpenAI REST API ({config.OPENAI_MODEL}) 호출 중...")
    resp = req.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code == 200:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return clean_html_output(content)
    else:
        raise RuntimeError(f"OpenAI API 호출 실패: HTTP {resp.status_code} {resp.text[:200]}")


def generate_with_perplexity(prompt: str, sys_prompt: str = SYSTEM_PROMPT) -> str:
    """
    Perplexity REST API를 호출하여 최신 실시간 웹 탐색 기반 HTML 리포트를 생성합니다.
    검색 출처(citations)가 있으면 본문 하단에 깔끔한 출처 링크 박스로 추가합니다.
    """
    import requests as req

    api_key = getattr(config, "PERPLEXITY_API_KEY", "").strip()
    if not api_key or api_key == "your_perplexity_api_key_here":
        raise ValueError("PERPLEXITY_API_KEY가 설정되지 않았습니다. .env 파일에 키를 입력해 주세요.")

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    model_name = getattr(config, "PERPLEXITY_MODEL", "sonar-pro") or "sonar-pro"
    
    # Perplexity 전용 지시사항 보강: 인라인 각주 번호 금지 및 HTML 태그 100% 완결
    pplx_sys_prompt = sys_prompt + """

[출력 형식 및 HTML 태그 엄수 규칙]:
1. 본문 작성 시 문장 중간이나 끝에 [1], [2], [11], [12] 같은 검색 인라인 각주 번호를 절대 삽입하지 마세요. 오직 깔끔하고 매끄러운 한글 문장으로만 작성하세요.
2. <table>, <tr>, <td>, <div>, <ul> 태그는 반드시 닫는 태그(</table>, </tr>, </td>, </div>, </ul>)를 빠짐없이 완벽하게 닫아 화면이 깨지지 않게 하세요.
"""

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": pplx_sys_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }

    logger.info(f"Perplexity API ({model_name}) 실시간 웹 탐색 호출 중...")
    resp = req.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code == 200:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        
        # 1. 본문 정제: [1], [11], [12] 같은 인라인 각주 번호 즉시 제거 및 태그 닫기 보정
        content = re.sub(r'\[\d+\]', '', content)
        html_out = clean_html_output(content)
        
        # 2. 실시간 웹 탐색 출처 링크가 있으면 테이블 바깥에 독립된 카드로 안전하게 추가
        if citations:
            citation_links = []
            for cit in citations[:6]:
                domain = cit.split("//")[-1].split("/")[0]
                citation_links.append(f"<li style='margin-bottom:4px;'><a href='{cit}' target='_blank' style='color:#2563eb; text-decoration:none;'>{domain}</a></li>")
            
            citation_html = f"""
<div style="clear:both; width:100%; box-sizing:border-box; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px 20px; margin:35px 0 20px 0; font-size:13px;">
  <strong style="color:#334155; display:block; margin-bottom:8px;">🔎 Perplexity 실시간 웹 검색 및 팩트체크 출처:</strong>
  <ul style="margin:0; padding-left:18px; color:#64748b; line-height:1.6;">
    {"".join(citation_links)}
  </ul>
</div>
"""
            # 앞선 HTML의 모든 테이블/블록 태그가 완전히 닫힌 후 독립 박스로 결합
            html_out = fix_unclosed_html_tags(html_out) + citation_html
            
        logger.info(f"Perplexity 응답 완료 (길이: {len(html_out)}자, 출처 {len(citations)}개)")
        return html_out
    else:
        raise RuntimeError(f"Perplexity API 호출 실패: HTTP {resp.status_code} {resp.text[:200]}")


def _generate_with_gemini_rest(prompt: str, image_paths: List[str], sys_prompt: str = "") -> str:
    """
    구글 Gemini REST API를 직접 호출하여 이미지+텍스트로 HTML 포스팅을 생성합니다.
    google-generativeai 라이브러리를 거치지 않고, requests로 직접 HTTP 요청을 보냅니다.
    이렇게 하면 라이브러리 버전 호환성 문제를 완전히 우회할 수 있습니다.
    """
    import base64
    import os
    import requests as req

    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")

    api_key = config.GEMINI_API_KEY.strip()

    # 이미지들을 base64로 인코딩
    image_parts = []
    for img_path in image_paths:
        if not os.path.exists(img_path):
            logger.warning(f"이미지 파일을 찾을 수 없습니다: {img_path}")
            continue
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        image_parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_data
            }
        })

    if not image_parts:
        raise FileNotFoundError("유효한 이미지 파일이 없습니다.")

    # 요청 본문 구성: 텍스트 + 이미지들
    parts = [{"text": f"[시스템 지시사항: {sys_prompt}]\n\n{prompt}"}] + image_parts
    
    request_body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 3000
        }
    }

    # 여러 모델을 순차적으로 시도 (2026년 9월 기준 gemini-3.6-flash가 최신 정식 모델)
    models_to_try = [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    
    last_error = None
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        logger.info(f"Gemini REST API ({model_name}) 직접 호출 중... (이미지 {len(image_parts)}장)")
        
        try:
            resp = req.post(url, json=request_body, timeout=120)
            
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if text:
                    logger.info(f"[{model_name}] 모델로 성공! (응답 길이: {len(text)}자)")
                    return clean_html_output(text)
                else:
                    logger.warning(f"[{model_name}] 빈 응답 수신")
                    last_error = "빈 응답"
            elif resp.status_code == 429:
                error_msg = "Google Gemini 일일 무료 사용량(20회) 초과 (HTTP 429 Quota Exceeded)"
                logger.warning(f"[{model_name}] {error_msg}")
                last_error = error_msg
                # 429 쿼터 초과는 계정 전체 제한이므로 다른 모델을 시도하지 않고 즉시 백업(OpenAI)으로 전환
                break
            else:
                error_msg = resp.text[:200]
                logger.warning(f"[{model_name}] HTTP {resp.status_code}: {error_msg}")
                last_error = f"HTTP {resp.status_code}: {error_msg}"
                
        except Exception as e:
            logger.warning(f"[{model_name}] 요청 실패: {str(e)[:100]}")
            last_error = str(e)
            continue

    raise RuntimeError(f"Gemini 호출 실패: {last_error}")


def _generate_with_openai_vision(prompt: str, image_paths: List[str], sys_prompt: str = "") -> str:
    """
    OpenAI Vision API (gpt-4o-mini)를 requests로 직접 호출하여 이미지+텍스트로 HTML 포스팅을 생성합니다.
    """
    import base64
    import os
    import requests as req

    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")

    content_parts = [{"type": "text", "text": f"[시스템 지시사항: {sys_prompt}]\n\n{prompt}"}]
    
    for img_path in image_paths:
        if not os.path.exists(img_path):
            continue
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_data}", "detail": "low"}
        })

    model_name = config.OPENAI_MODEL or "gpt-4o-mini"
    logger.info(f"OpenAI Vision API ({model_name}) 직접 호출 중... (이미지 {len(image_paths)}장)")
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY.strip()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_parts}],
        "temperature": 0.5,
        "max_tokens": 3000
    }

    resp = req.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code == 200:
        data = resp.json()
        result = data["choices"][0]["message"]["content"]
        if not result:
            raise RuntimeError("OpenAI로부터 비어있는 응답을 받았습니다.")
        logger.info("OpenAI Vision 호출 성공!")
        return clean_html_output(result)
    else:
        raise RuntimeError(f"OpenAI Vision API 호출 실패: HTTP {resp.status_code} {resp.text[:200]}")


def generate_daily_life_post(image_paths: Union[str, List[str]], user_caption: str, image_urls: Optional[List[str]] = None) -> str:
    """
    업로드된 사진(들)과 사장님의 짧은 코멘트를 기반으로 '나의 일상/육아' 블로그 포스팅 초안을 생성합니다.
    기본적으로 Gemini REST API를 사용하며, 실패하거나 OpenAI 설정 시 자동 교체 지원합니다.
    """
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    
    url_info = ""
    if image_urls and len(image_urls) == len(image_paths):
        url_info = "아래는 첨부된 각 사진들의 실제 이미지 호스팅 주소(URL)입니다. HTML 본문 작성 시 각 상황에 맞는 사진을 이 주소를 사용하여 `<img src='...' style='max-width:100%; border-radius:10px; margin:20px 0;'>` 형태로 반드시 적절한 문단 사이사이에 삽입해 주세요.\n"
        for i, url in enumerate(image_urls):
            url_info += f"- {i+1}번째 사진 URL: {url}\n"

    user_prompt = f"""첨부된 사진(들)과 아래의 짤막한 메모를 보고, 개인 블로그(일상/육아)에 어울리는 스토리텔링 포스팅 초안을 작성해 주세요.

[사장님의 메모]: {user_caption if user_caption else '(메모 없음)'}

{url_info}

[작성 및 디자인 가이드라인]
1. 첨부된 사진들의 시간적 흐름이나 상황을 유추하여, 친근하고 따뜻한 블로거 말투(~했어요, ~입니다)로 자연스럽게 이야기를 풀어주세요.
2. 억지스러운 서론 없이 바로 일상 이야기로 들어갈 것.
3. 제공된 사진 URL들이 있다면, 이야기 흐름에 맞춰 알맞은 문단 아래에 `<img src="사진 URL" style="max-width:100%; border-radius:10px; margin:20px 0;">` 형태로 이미지를 모두 삽입해 주세요. (가장 첫 번째 사진은 썸네일로도 쓰이므로 본문 최상단에 굳이 중복해서 넣지 않아도 됩니다. 글 중간중간에 배치해 주세요.)
4. 글 하단에는 블로그 주인이 최종적으로 자신의 진짜 느낀점이나 결론을 덧붙일 수 있도록 아래와 같은 문구를 눈에 띄게 배치할 것:
   <div style="background:#fffbeb; border:2px dashed #f59e0b; padding:20px; margin:25px 0; color:#b45309; font-weight:bold; text-align:center; border-radius:8px;">
   [사장님의 찐후기 또는 추가하고 싶은 내용을 자유롭게 적어주세요!]
   </div>
5. 모든 HTML 태그(<div>, <p> 등)는 짝을 맞춰 정확하게 닫을 것 (화면 깨짐 방지).
6. 마크다운(```html) 기호 없이 순수 HTML만 출력할 것.
"""
    sys_prompt = "너는 따뜻하고 유쾌한 글솜씨를 가진 파워 블로거야. 주어진 사진들을 보고 사람들의 공감을 이끌어낼 수 있는 일상/육아 스토리텔링 포스팅을 멋지게 작성해 줘."
    
    provider = config.LLM_PROVIDER.lower()
    
    if provider == "openai":
        primary_fn = lambda: _generate_with_openai_vision(user_prompt, image_paths, sys_prompt=sys_prompt)
        backup_fn = lambda: _generate_with_gemini_rest(user_prompt, image_paths, sys_prompt=sys_prompt) if config.GEMINI_API_KEY else None
    else:
        primary_fn = lambda: _generate_with_gemini_rest(user_prompt, image_paths, sys_prompt=sys_prompt)
        backup_fn = lambda: _generate_with_openai_vision(user_prompt, image_paths, sys_prompt=sys_prompt) if config.OPENAI_API_KEY else None

    try:
        return primary_fn()
    except Exception as primary_err:
        logger.warning(f"기본 AI ({provider}) 생성 실패 ({primary_err}), 백업 AI 전환 시도...")
        try:
            if backup_fn:
                return backup_fn()
            else:
                raise primary_err
        except Exception as backup_err:
            logger.error(f"백업 AI 생성도 실패: {backup_err}", exc_info=True)
            return f"<h1>[시스템 임시 저장] 오류 발생</h1><p>기본 AI: {str(primary_err)[:100]}<br>백업 AI: {str(backup_err)[:100]}</p>"


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

    provider = getattr(config, "STOCK_LLM_PROVIDER", config.LLM_PROVIDER).lower()
    logger.info(f"AI 증시 추론 엔진 가동 (선택된 공급자: {provider})")

    try:
        if provider == "perplexity":
            try:
                html_result = generate_with_perplexity(user_prompt)
            except Exception as pplx_err:
                logger.warning(f"Perplexity 생성 실패 ({pplx_err}), 안전 폴백(Gemini)으로 자동 전환합니다.")
                html_result = generate_with_gemini(user_prompt)
        elif provider == "openai":
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

[구글 SEO 및 애드센스 승인 최적화 작성 가이드라인 - 엄격 준수]
1. 헤드라인:
   최상단에 눈길을 사로잡는 매력적인 <h1>[모닝 브리핑] 간밤의 미 증시 자금 흐름과 오늘 국장 시초가 공략 뷰</h1> 작성.

2. 📊 [간밤의 미 증시 & 매크로 핵심 스코어보드]:
   미국 섹터별 흐름과 국채 금리, 원유 가격을 한눈에 볼 수 있는 세련된 HTML <table>을 배치할 것.
   (스타일: table style="width:100%; border-collapse:collapse; margin:20px 0; background:#f8fafc; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;")
   - 컬럼: 거시지표·섹터 / 수치 및 등락 / 글로벌 자금 흐름 상태(🟢자금유입, 🔴차익실현 등 이모지 활용)

3. 💡 [오늘 국장 핵심 뷰 (3줄 요약 박스)]:
   분석에 앞서 간밤 미국장 데이터를 종합하여 오늘 한국 시장(국장)의 자금 이동 경로와 시초가 공략 포인트를 3줄로 명확하게 요약할 것.
   <div style="background:#f0f7ff; border-left:5px solid #2563eb; padding:16px 20px; border-radius:6px; margin:25px 0;">

4. 3대 심층 논리 분석 섹션 (<h2> 태그 활용 - 단순 데이터 나열 절대 금지, 1,500자 이상의 풍부한 논리적 서술문 작성):
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">1. 글로벌 매크로 지표 분석: 미국채 금리 & 원유가 국장에 미칠 유동성 파급력</h2>
     * 단순히 금리 몇 %, 유가 몇 달러라는 숫자 나열을 절대 지양하고, 해당 지표의 변동이 오늘 환율과 외국인/기관의 국장 순매수 여력에 미칠 구체적 영향을 인과관계 중심으로 최소 2문단 이상 논리 분석.
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">2. 미국 11대 섹터 자금 쏠림과 오늘 한국 증시 유망·주의 섹터 맵핑</h2>
     * 간밤 미국에서 자금이 강하게 쏠린 섹터(예: 테크/반도체, 에너지 등)와 부진했던 섹터를 비교 분석하고, 이것이 오늘 개장할 한국 증시의 관련 밸류체인 대표주에 어떤 동조화/디커플링을 가져올지 수급 연결 분석.
   - <h2 style="color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-top:35px;">3. 오늘 한국 시장(국장) 실전 투자 전략 & 시초가 관전 포인트</h2>
     * 오늘 코스피/코스닥의 예상 개장 시초가 분위기, 갭상승 시 추격매수 자제 구간, 눌림목에서 자금 유입이 기대되는 수혜 테마 등 실전 투자자의 독창적인 관점(View)을 2~3개 문단으로 상세 서술.

5. 📅 [오늘의 주요 글로벌 경제 캘린더 & 변동성 대비]:
   - 데이터가 있을 경우 세련된 HTML <table>(발표 시간 / 국가 / 지표명 / 중요도 / 예상치 / 직전치)로 정리할 것.
   - 모바일 깨짐 방지를 위해 반드시 `<div style="overflow-x:auto; width:100%;">`로 테이블을 감싸고, `</table>`과 `</div>`를 반드시 끝까지 완벽하게 닫을 것.
   - 표 하단에 해당 지표 발표 시 장중 변동성에 대비한 리스크 관리 팁 1~2문단 추가.

6. 하단 출처 및 면책조항 카드:
   - <div style="background:#f1f5f9; padding:15px; border-radius:6px; font-size:13px; color:#64748b; margin-top:40px;">
     <strong>⚠️ 투자 유의사항:</strong> 본 리포트는 글로벌 매크로 및 거래소 데이터를 기반으로 작성된 독자적 분석 참고 자료이며, 모든 투자의 최종 결정과 책임은 투자자 본인에게 있습니다.
     </div>

7. 출력 규칙:
   - 마크다운 코드 블럭(```html) 없이 오직 완성된 순수 HTML 태그 문자열만 출력할 것.
   - [1], [2], [11] 같은 인라인 각주 번호는 문장에 절대 넣지 말 것.
   - 모든 <table>, <div>, <tr>, <td> 태그를 끝까지 완벽하게 닫을 것.
"""

    provider = getattr(config, "STOCK_LLM_PROVIDER", config.LLM_PROVIDER).lower()
    logger.info(f"AI 모닝 증시 추론 엔진 가동 (선택된 공급자: {provider})")

    morning_sys_prompt = """너는 글로벌 매크로 지표(미국채 금리, 원유, 달러)와 미국 11대 섹터의 자금 흐름을 면밀히 추적하여, 오늘 한국 주식시장(코스피/코스닥)의 개장 전 방향성과 유망 섹터를 족집게처럼 짚어주는 실전 금융 분석 전문가야.
구글 검색 로봇은 단순 복사 및 수치 나열 문서를 '가치 없는 저품질 문서'로 분류하여 애드센스 승인을 거절합니다.
따라서 제공된 정량 데이터(지표, 섹터, 뉴스)를 바탕으로, 단순 나열을 완전히 배제하고 "자금 흐름의 논리적 인과관계와 오늘 국장 시초가 대응 시나리오"를 1,500자 이상의 전문적인 리포트 형식으로 완성도 높게 작성해야 해.
말투는 딱딱한 기사체가 아니라, 본인의 관점(View)을 명확하게 제시하는 전문 투자 블로거의 친근하면서도 신뢰도 높은 어조(~인 것으로 보임, ~라고 분석됨, ~습니다)를 사용해 줘.
"안녕하세요", "저는 전문가입니다" 같은 서론은 모두 빼고, 바로 제목과 본론부터 시작해."""

    try:
        if provider == "perplexity":
            try:
                html_result = generate_with_perplexity(user_prompt, sys_prompt=morning_sys_prompt)
            except Exception as pplx_err:
                logger.warning(f"Perplexity 모닝 시황 생성 실패 ({pplx_err}), 안전 폴백(Gemini)으로 자동 전환합니다.")
                html_result = generate_with_gemini(user_prompt, sys_prompt=morning_sys_prompt)
        elif provider == "openai":
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
    
    provider = getattr(config, "STOCK_LLM_PROVIDER", config.LLM_PROVIDER).lower()
    try:
        if provider == "perplexity":
            try:
                return generate_with_perplexity(user_prompt, sys_prompt=sys_prompt)
            except Exception as pplx_err:
                logger.warning(f"Perplexity 주간 시황 생성 실패 ({pplx_err}), 안전 폴백(Gemini)으로 자동 전환합니다.")
                return generate_with_gemini(user_prompt, sys_prompt=sys_prompt)
        elif provider == "openai":
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

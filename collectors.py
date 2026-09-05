"""
데이터 수집부 (Data Collection Module)
- feedparser 및 requests를 활용하여 주요 금융/경제 키워드 RSS 피드 수집
- 구글 뉴스 RSS 피드 파싱 및 데이터 정제
"""

import logging
import urllib.parse
from typing import List, Dict, Any
import feedparser

logger = logging.getLogger(__name__)

DEFAULT_KEYWORDS = [
    "국내 증시",
    "비트코인 시황",
    "나스닥",
    "유가",
    "금리",
    "달러 인덱스",
    "채권",
    "속보"
]

US_KEYWORDS = [
    "미국 증시",
    "S&P500",
    "나스닥",
    "미국 연준",
    "미국 국채"
]

TREND_KEYWORDS = [
    "육아템 추천",
    "국민 육아템",
    "육아 트렌드",
    "신생아 용품",
    "육아 꿀팁"
]

def fetch_rss_news(keyword: str, max_items: int = 3) -> List[Dict[str, Any]]:
    """
    지정된 키워드로 Google News RSS 피드를 호출하여 최신 기사를 수집합니다.
    
    Args:
        keyword (str): 검색할 키워드
        max_items (int): 키워드당 수집할 최대 기사 수
        
    Returns:
        List[Dict[str, Any]]: 정제된 기사 목록 [{title, link, published, summary, keyword}]
    """
    encoded_kw = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=ko&gl=KR&ceid=KR:ko"
    
    logger.info(f"[{keyword}] 키워드로 RSS 피드 수집 시작... (URL: {rss_url})")
    
    articles = []
    try:
        # feedparser를 통한 RSS 요청 및 파싱
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            logger.warning(f"[{keyword}] RSS 피드 파싱 경고/오류: {feed.bozo_exception}")
            
        entries = feed.entries[:max_items]
        for entry in entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            published = getattr(entry, "published", "").strip()
            summary = getattr(entry, "summary", "").strip()
            
            # HTML 태그 제거 등 간단한 텍스트 정제
            articles.append({
                "keyword": keyword,
                "title": title,
                "link": link,
                "published": published,
                "summary": summary
            })
            
        logger.info(f"[{keyword}] 기사 {len(articles)}건 수집 완료.")
    except Exception as e:
        logger.error(f"[{keyword}] RSS 수집 중 예외 발생: {e}", exc_info=True)
        
    return articles


def collect_market_news(keywords: List[str] = None, max_per_keyword: int = 3) -> List[Dict[str, Any]]:
    """
    전체 대상 키워드를 순회하며 금융 시황 기사를 종합 수집합니다. (중복 기사 필터링 포함)
    
    Args:
        keywords (List[str], optional): 수집 키워드 목록
        max_per_keyword (int): 키워드별 수집 건수
        
    Returns:
        List[Dict[str, Any]]: 총 5~12개 내외의 수집된 최신 뉴스 리스트
    """
    if keywords is None:
        keywords = DEFAULT_KEYWORDS
        
    all_news = []
    seen_titles = set()
    
    logger.info(f"총 {len(keywords)}개 키워드에 대한 데이터 수집 파이프라인 가동...")
    
    for kw in keywords:
        try:
            items = fetch_rss_news(kw, max_items=max_per_keyword)
            for item in items:
                # 기사 제목 기반 중복 필터링
                if item["title"] not in seen_titles:
                    seen_titles.add(item["title"])
                    all_news.append(item)
        except Exception as e:
            logger.error(f"키워드 [{kw}] 처리 중 예기치 못한 에러: {e}")
            continue
            
    logger.info(f"최종 중복 제거 후 총 {len(all_news)}건의 뉴스 기사 확보 완료.")
    return all_news

def collect_us_market_news(max_per_keyword: int = 3) -> List[Dict[str, Any]]:
    """
    미국 시장 중심으로 뉴스를 수집합니다.
    """
    return collect_market_news(keywords=US_KEYWORDS, max_per_keyword=max_per_keyword)

def collect_trend_news(max_per_keyword: int = 3) -> List[Dict[str, Any]]:
    """
    일상/육아 트렌드 중심으로 뉴스를 수집합니다.
    """
    return collect_market_news(keywords=TREND_KEYWORDS, max_per_keyword=max_per_keyword)


def fetch_us_sectors() -> List[Dict[str, Any]]:
    """
    stock.marsticker.com/api/us-sectors에서 미국 11대 섹터 데이터를 수집합니다.
    """
    url = "https://stock.marsticker.com/api/us-sectors"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            logger.info(f"미국 11대 섹터 데이터 {len(data)}개 수집 완료.")
            return data
    except Exception as e:
        logger.error(f"미국 섹터 데이터 수집 실패: {e}")
    return []

def fetch_us_macro() -> Dict[str, Any]:
    """
    야후 파이낸스를 통해 미국채 10년물(^TNX), 13주물(^IRX), WTI 원유(CL=F) 데이터를 수집합니다.
    """
    symbols = {
        "US_10Y": "^TNX",
        "US_13W": "^IRX",
        "WTI_OIL": "CL=F"
    }
    results = {}
    for name, sym in symbols.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta["regularMarketPrice"]
                chg_pct = meta.get("regularMarketChangePercent", 0)
                results[name] = {"price": price, "change_pct": chg_pct}
        except Exception as e:
            logger.warning(f"야후 파이낸스 데이터 수집 실패 ({name}): {e}")
            results[name] = {"price": 0.0, "change_pct": 0.0}
    
    logger.info(f"미국 거시 지표 수집 완료: {results}")
    return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    news_list = collect_market_news()
    for idx, n in enumerate(news_list, 1):
        print(f"[{idx}] [{n['keyword']}] {n['title']} ({n['published']})")

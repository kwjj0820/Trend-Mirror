import os
import time
import pandas as pd
import datetime as dt
from typing import List, Dict, Any, Optional, Tuple
import requests
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT/".env")


NAVER_CLIENT_ID = (os.getenv("NAVER_CLIENT_ID") or "").strip()
NAVER_CLIENT_SECRET = (os.getenv("NAVER_CLIENT_SECRET") or "").strip()

print(NAVER_CLIENT_ID)
NAVER_BLOG_SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"


class NaverBlogClientError(RuntimeError):
    pass


def _headers() -> Dict[str, str]:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise NaverBlogClientError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 이 비어있음 (.env 또는 환경변수 확인)"
        )
    return {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }


def _get(url: str, params: dict, timeout: int = 20, retries: int = 3, backoff: float = 1.2) -> requests.Response:
    last = None
    for t in range(retries):
        r = requests.get(url, headers=_headers(), params=params, timeout=timeout)
        last = r

        # 429: too many requests / 5xx: server error
        if r.status_code in (429,) or (500 <= r.status_code <= 599):
            time.sleep(backoff * (t + 1))
            continue

        return r

    return last  


def _parse_postdate(postdate: str) -> Optional[dt.date]:
    """
    postdate: 'YYYYMMDD' 형태 (네이버 블로그 검색 API)
    """
    if not postdate or len(postdate) != 8:
        return None
    try:
        y = int(postdate[0:4])
        m = int(postdate[4:6])
        d = int(postdate[6:8])
        return dt.date(y, m, d)
    except Exception:
        return None


def _days_ago(d: Optional[dt.date]) -> float:
    if not d:
        return 9999.0
    today = dt.date.today()
    return float((today - d).days)


def naver_blog_search(
    query: str,
    display: int = 100,
    start: int = 1,
    sort: str = "date",  # date | sim
) -> Dict[str, Any]:
    """
    네이버 블로그 검색 Open API 호출 (원본 JSON 반환)
    """
    if display < 1 or display > 100:
        raise ValueError("display는 1~100 범위")
    if start < 1 or start > 1000:
        raise ValueError("start는 1~1000 범위 (API 제한)")

    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": sort,
    }

    r = _get(NAVER_BLOG_SEARCH_URL, params=params, timeout=20, retries=3)
    if r is None:
        raise NaverBlogClientError("네이버 API 호출 실패 (응답 없음)")
    if r.status_code != 200:
        raise NaverBlogClientError(f"네이버 API 오류: {r.status_code} / {r.text}")

    return r.json()


def collect_naver_blog_candidates(
    queries: List[str],
    days: int = 7,
    per_query: int = 200,
    sort: str = "date",
    sleep_sec: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    여러 쿼리로 블로그 검색 결과를 모아
    - 중복 URL 제거
    - postdate 기준 최근 days일 이내만 필터
    - 공통 스키마로 반환

    반환 스키마(예시):
    {
      "source": "naver_blog",
      "query": "...",
      "title": "...",
      "description": "...",
      "link": "...",
      "bloggername": "...",
      "postdate": "YYYYMMDD",
      "post_date": date | None,
      "days_ago": float
    }
    """
    out: List[Dict[str, Any]] = []
    seen_links = set()

    for q in queries:
        fetched = 0
        start = 1

        while fetched < per_query:
            display = min(100, per_query - fetched)
            data = naver_blog_search(query=q, display=display, start=start, sort=sort)
            items = data.get("items", []) or []
            if not items:
                break

            for it in items:
                link = (it.get("link") or "").strip()
                if not link or link in seen_links:
                    continue

                postdate = (it.get("postdate") or "").strip()
                post_d = _parse_postdate(postdate)
                ago = _days_ago(post_d)

                if ago > days:
                    if sort == "date":
                        items = []  
                    continue

                seen_links.add(link)

                out.append({
                    "source": "naver_blog",
                    "query": q,
                    "title": (it.get("title") or ""),
                    "description": (it.get("description") or ""),
                    "link": link,
                    "bloggername": (it.get("bloggername") or ""),
                    "postdate": postdate,
                    "post_date": post_d,
                    "days_ago": ago,
                })

            fetched += len(items)
            start += len(items)

            # 네이버 Open API start는 최대 1000 제한
            if start > 1000:
                break

            time.sleep(sleep_sec)

            if not items and sort == "date":
                break

    # 최신순 정렬
    out.sort(key=lambda x: (x.get("days_ago", 9999.0), x.get("link", "")))
    return out


FOOD_HINT_KEYWORDS = [
    "먹방", "맛집", "디저트", "카페", "베이커리", "빵", "커피", "신상",
    "편의점", "후기", "리뷰", "레시피", "요리", "메뉴", "핫플",
    "마라", "탕후루", "두바이", "크루아상", "라면", "치킨", "떡볶이",
]

def filter_food_posts(
    posts: List[Dict[str, Any]],
    keywords: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    kws = keywords or FOOD_HINT_KEYWORDS
    out = []
    for p in posts:
        text = f"{p.get('title','')} {p.get('description','')}"
        if any(k in text for k in kws):
            out.append(p)
    return out


if __name__ == "__main__":
    qs = ["요즘 유행 음식", "요즘 핫한 디저트", "편의점 신상 먹방"]
    raw = collect_naver_blog_candidates(qs, days=7, per_query=200, sort="date")
    food = filter_food_posts(raw)
    df = pd.DataFrame(food)

    if "post_date" in df.columns:
        df["post_date"] = df["post_date"].astype(str)
        preferred = ["days_ago", "postdate", "post_date", "title", "description", "bloggername", "link", "query", "source"]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    df = df[cols]

    data_dir = os.path.join("data")
    os.makedirs(data_dir, exist_ok=True)

    out_path = os.path.join(data_dir, "naver_blog_food_candidates_7d.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print("saved:", out_path, "rows:", len(df))

    # print("raw:", len(raw), "food:", len(food))
    # for r in food[:5]:
    #     print(r["postdate"], r["title"], r["link"])

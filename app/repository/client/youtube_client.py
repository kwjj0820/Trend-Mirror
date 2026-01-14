import os, time, requests, datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

YOUTUBE_API_KEY = (os.getenv("YOUTUBE_API_KEY") or "").strip()
BASE = "https://www.googleapis.com/youtube/v3"

if not YOUTUBE_API_KEY:
    raise RuntimeError("YOUTUBE_API_KEY가 비어있음 (.env 확인)")

def _get(url: str, params: dict, timeout=30, retries=3):
    for t in range(retries):
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code in (403, 429):  # quota/too many
            time.sleep(1.5 * (t + 1))
            continue
        return r
    return r

def yt_search(query: str, max_results: int = 50, days: int = 30, pages: int = 1) -> List[Dict[str, Any]]:
    
    published_after = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat("T") + "Z"

    items_out = []
    page_token = None

    for _ in range(pages):
        params = {
            "key": YOUTUBE_API_KEY,
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
            "publishedAfter": published_after,
            "relevanceLanguage": "ko",
            "regionCode": "KR",
            "safeSearch": "none",
            "order": "date",
        }
        if page_token:
            params["pageToken"] = page_token

        r = _get(f"{BASE}/search", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        for it in data.get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            sn = it.get("snippet") or {}
            if not vid or not sn:
                continue
            items_out.append({
                "video_id": vid,
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "published_at": sn.get("publishedAt", ""),
                "channel_title": sn.get("channelTitle", ""),
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return items_out

def yt_videos_stats(video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for i in range(0, len(video_ids), 50): 
        chunk = ",".join(video_ids[i:i+50])
        params = {
            "key": YOUTUBE_API_KEY,
            "part": "statistics",
            "id": chunk
        }
        r = _get(f"{BASE}/videos", params=params, timeout=30)
        r.raise_for_status()

        for it in r.json().get("items", []):
            vid = it.get("id")
            stat = it.get("statistics", {}) or {}
            if not vid:
                continue
            out[vid] = {
                "viewCount": int(stat.get("viewCount", 0) or 0),
                "likeCount": int(stat.get("likeCount", 0) or 0) if "likeCount" in stat else 0,
                "commentCount": int(stat.get("commentCount", 0) or 0) if "commentCount" in stat else 0,
            }
    return out

def days_since(published_at: str) -> float:
    if not published_at:
        return 30.0
    dt = datetime.datetime.fromisoformat(published_at.replace("Z","+00:00"))
    delta = datetime.datetime.now(datetime.timezone.utc) - dt
    return max(delta.total_seconds() / 86400.0, 0.5)

def trend_score(stats: Dict[str, Any], published_at: str) -> float:
    v = stats.get("viewCount", 0)
    l = stats.get("likeCount", 0)
    c = stats.get("commentCount", 0)
    d = days_since(published_at)

    views_per_day = v / d
    like_ratio = (l / v) if v else 0
    comment_ratio = (c / v) if v else 0
    return (views_per_day * 0.6) + (like_ratio * 100000 * 0.2) + (comment_ratio * 100000 * 0.2)
"""
현재 30일 기준임. 50개씩 페이지 3개
"""
def collect_youtube_trend_candidates(query: str, days=30, per_query=50, pages=1) -> List[Dict[str, Any]]:
    if not query:
        # Fallback to a default query if none is provided
        queries = ["요즘 유행"]
    else:
        # Use only the provided query for broader search scope
        queries = [query]

    videos = []
    seen = set()

    for q in queries:
        for v in yt_search(q, max_results=per_query, days=days, pages=pages):
            if v["video_id"] in seen:
                continue
            seen.add(v["video_id"])
            videos.append(v)

    stats_map = yt_videos_stats([v["video_id"] for v in videos])

    for v in videos:
        st = stats_map.get(v["video_id"], {"viewCount":0,"likeCount":0,"commentCount":0})
        v.update(st)
        v["score"] = trend_score(st, v["published_at"])

    videos.sort(key=lambda x: x["score"], reverse=True)
    return videos

def collect_youtube_trend_candidates_df(query: str, days=30, per_query=50, pages=1) -> pd.DataFrame:
    videos = collect_youtube_trend_candidates(query=query, days=days, per_query=per_query, pages=pages)
    df = pd.DataFrame(videos)

    preferred = [
        "score","video_id","title","channel_title","published_at",
        "viewCount","likeCount","commentCount","description",
    ]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    df = df[cols]

    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    for c in ["viewCount","likeCount","commentCount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)

    return df

if __name__ == "__main__":
    df = collect_youtube_trend_candidates_df(days=30, per_query=50, pages=1)
    print(df.head(10))
    data_dir = os.path.join("data")
    os.makedirs(data_dir, exist_ok=True)
    
    out_path = os.path.join(data_dir, "youtube_trend_candidates.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print("saved:", len(df))

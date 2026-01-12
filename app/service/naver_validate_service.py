# app/service/naver_validate_service.py
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd


def _root_dir() -> Path:
    # app/service/naver_validate_service.py -> service -> app -> project root
    return Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    # 지금 네가 쓰는 data 경로: app/repository/client/data
    return _root_dir() / "app" / "repository" / "client" / "data"


def _clean_html(s: str) -> str:
    if not isinstance(s, str):
        return ""
    # 네이버 검색 결과에 <b>태그가 섞여 나오는 경우가 흔함
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _load_youtube_candidates(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    # 필수 컬럼 체크 (너 CSV 컬럼명에 맞춰 대충 호환)
    # title, description, channel_title, score 등
    for col in ["title", "description"]:
        if col not in df.columns:
            df[col] = ""
    if "score" not in df.columns:
        df["score"] = 0.0

    df["title"] = df["title"].astype(str).map(_clean_html)
    df["description"] = df["description"].astype(str).map(_clean_html)

    # 합친 텍스트 (키워드 탐지용)
    df["yt_text"] = (df["title"].fillna("") + " " + df["description"].fillna("")).str.strip()
    return df


def _load_naver_posts(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    for col in ["title", "description", "bloggername", "link", "postdate", "days_ago"]:
        if col not in df.columns:
            df[col] = ""

    df["title"] = df["title"].astype(str).map(_clean_html)
    df["description"] = df["description"].astype(str).map(_clean_html)

    df["bloggername"] = df["bloggername"].astype(str)
    df["link"] = df["link"].astype(str)
    df["postdate"] = df["postdate"].astype(str)
    # days_ago가 숫자로 들어오게 보정
    df["days_ago"] = pd.to_numeric(df["days_ago"], errors="coerce").fillna(9999).astype(int)

    df["nv_text"] = (df["title"].fillna("") + " " + df["description"].fillna("")).str.strip()
    return df


def _extract_keywords_simple(
    yt_df: pd.DataFrame,
    top_k: int = 30,
    min_videos: int = 2,
) -> pd.DataFrame:
    """
    LLM 없이도 돌아가는 "간단 키워드 후보" 생성기.
    - 유튜브 title/description에서 한글/숫자 토큰 추출
    - 불용어 제거
    - 영상 수/score 합으로 랭킹
    """
    # 매우 기본 불용어(필요하면 늘리면 됨)
    stop = set([
        "먹방", "맛집", "브이로그", "vlog", "리뷰", "후기", "추천", "신상", "요즘", "유행",
        "핫한", "핫플", "편의점", "음식", "디저트", "레시피", "요리", "도전", "모음",
        "ASMR", "asmr", "shorts", "쇼츠", "전국", "한국", "서울", "부산", "대구",
        "진짜", "최고", "레전드", "간단", "초간단"
    ])

    token_re = re.compile(r"[가-힣0-9]{2,}")  # 2글자 이상 한글/숫자

    rows = []
    for _, r in yt_df.iterrows():
        text = str(r.get("yt_text", ""))
        score = float(r.get("score", 0.0) or 0.0)
        tokens = token_re.findall(text)
        # 정제
        tokens = [t for t in tokens if t not in stop and len(t) <= 15]
        # 중복 제거(한 영상 내)
        for t in set(tokens):
            rows.append((t, score))

    if not rows:
        return pd.DataFrame(columns=["keyword", "yt_videos", "yt_score_sum"])

    tmp = pd.DataFrame(rows, columns=["keyword", "score"])
    agg = tmp.groupby("keyword", as_index=False).agg(
        yt_videos=("keyword", "size"),
        yt_score_sum=("score", "sum"),
    )

    # 영상 수가 너무 적은 키워드는 제거
    agg = agg[agg["yt_videos"] >= min_videos].copy()

    # 랭킹: score 합 우선, 다음 videos
    agg.sort_values(["yt_score_sum", "yt_videos"], ascending=False, inplace=True)
    return agg.head(top_k).reset_index(drop=True)


def _match_keywords_to_naver(
    naver_df: pd.DataFrame,
    keywords: List[str],
) -> pd.DataFrame:
    
    """
    네이버 글별로 매칭된 키워드 목록 생성
    """

    matched = []
    for _, r in naver_df.iterrows():
        text = str(r.get("nv_text", ""))
        hits = [k for k in keywords if k and (k in text)]
        matched.append("|".join(hits) if hits else "")
    out = naver_df.copy()
    out["matched_keywords"] = matched
    out["match_count"] = out["matched_keywords"].apply(lambda s: 0 if not s else len(s.split("|")))
    return out


def _keyword_stats_from_labeled(
    labeled_df: pd.DataFrame,
    keywords: List[str],
    recent_days: int = 2
) -> pd.DataFrame:
    """
    키워드별 blog_posts / unique_bloggers / recent_posts_nd 생성
    """

    rows = []
    for _, r in labeled_df.iterrows():
        mk = r.get("matched_keywords", "")
        if not isinstance(mk, str) or not mk:
            continue
        for k in mk.split("|"):
            if k:
                rows.append({
                    "keyword": k,
                    "bloggername": r.get("bloggername", ""),
                    "link": r.get("link", ""),
                    "days_ago": int(r.get("days_ago", 9999) or 9999),
                })

    if not rows:
        return pd.DataFrame(columns=["keyword", "blog_posts", "unique_bloggers", f"recent_posts_{recent_days}d", "spread_score"])

    tmp = pd.DataFrame(rows)
    tmp["days_ago"] = pd.to_numeric(tmp["days_ago"], errors="coerce").fillna(9999).astype(int)

    agg = tmp.groupby("keyword", as_index=False).agg(
        blog_posts=("link", "nunique"),
        unique_bloggers=("bloggername", "nunique"),
        **{f"recent_posts_{recent_days}d": ("days_ago", lambda s: int((s <= recent_days).sum()))}
    )

    recent_col = f"recent_posts_{recent_days}d"
    agg["spread_score"] = (
        agg["blog_posts"] * 1.0 +
        agg["unique_bloggers"] * 0.7 +
        agg[recent_col] * 0.5
    )

    agg.sort_values(["spread_score", "blog_posts", "unique_bloggers"], ascending=False, inplace=True)
    return agg.reset_index(drop=True)


def main(
    youtube_csv: Optional[Path] = None,
    naver_csv: Optional[Path] = None,
    top_k_keywords: int = 30,
    min_videos: int = 2,
    recent_days: int = 2,
):
    data_dir = _data_dir()
    youtube_csv = youtube_csv or (data_dir / "youtube_trend_candidates.csv")
    naver_csv = naver_csv or (data_dir / "naver_blog_food_candidates_7d.csv")

    if not youtube_csv.exists():
        raise FileNotFoundError(f"유튜브 CSV 없음: {youtube_csv}")
    if not naver_csv.exists():
        raise FileNotFoundError(f"네이버 CSV 없음: {naver_csv}")

    yt_df = _load_youtube_candidates(youtube_csv)
    nv_df = _load_naver_posts(naver_csv)

    # 1) 유튜브 기반 키워드 후보(간단 버전)
    kw_df = _extract_keywords_simple(yt_df, top_k=top_k_keywords, min_videos=min_videos)
    keywords = kw_df["keyword"].astype(str).tolist()

    # 2) 네이버 글에 키워드 매칭
    labeled = _match_keywords_to_naver(nv_df, keywords)

    # 3) 키워드 확산 통계
    stats = _keyword_stats_from_labeled(labeled, keywords, recent_days=recent_days)

    # 4) 결과 저장
    out_kw = data_dir / "youtube_trend_keywords_simple.csv"
    out_labeled = data_dir / "naver_blog_posts_7d_labeled.csv"
    out_stats = data_dir / "naver_blog_keyword_stats_7d.csv"

    kw_df.to_csv(out_kw, index=False, encoding="utf-8-sig")
    labeled.to_csv(out_labeled, index=False, encoding="utf-8-sig")
    stats.to_csv(out_stats, index=False, encoding="utf-8-sig")

    print("saved:", out_kw, "rows:", len(kw_df))
    print("saved:", out_labeled, "rows:", len(labeled))
    print("saved:", out_stats, "rows:", len(stats))

    print("\nTOP spread keywords:")
    print(stats.head(15))


if __name__ == "__main__":
    main()

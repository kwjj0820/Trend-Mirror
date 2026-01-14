from pathlib import Path
from langgraph.graph import StateGraph, END
from app.agents.state import TMState
from app.core.logger import logger
from app.repository.client.youtube_client import collect_youtube_trend_candidates_df

def _data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "repository" / "client" / "data"

def youtube_collect_node(state: TMState) -> dict:
    logger.info("--- (YC) YouTube Collect Node ---")
    days = int(state.get("yt_days", 30))
    per_query = int(state.get("yt_per_query", 50))
    pages = int(state.get("yt_pages", 3))

    df = collect_youtube_trend_candidates_df(days=days, per_query=per_query, pages=pages)

    d = _data_dir()
    d.mkdir(parents=True, exist_ok=True)
    out = d / "youtube_trend_candidates.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")

    logger.info(f"(YC) saved: {out} rows={len(df)}")
    # keyword_extract 노드가 csv_path를 읽으니까 같이 세팅
    return {"youtube_csv_path": str(out), "csv_path": str(out), "error": None}

workflow = StateGraph(TMState)
workflow.add_node("youtube_collect", youtube_collect_node)
workflow.set_entry_point("youtube_collect")
workflow.add_edge("youtube_collect", END)
youtube_collect_graph = workflow.compile()

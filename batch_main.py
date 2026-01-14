from app.agents.batch_workflow import batch_graph

if __name__ == "__main__":
    state = {
        "yt_days": 30,
        "yt_per_query": 50,
        "yt_pages": 3,
        "nv_days": 7,
        "nv_per_query": 200,
    }
    out = batch_graph.invoke(state)
    print(out)

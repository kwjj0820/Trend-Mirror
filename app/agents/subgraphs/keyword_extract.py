# app/agents/subgraphs/keyword_extract.py
import pandas as pd
import json
from langgraph.graph import StateGraph, END
from tqdm import tqdm

from app.agents.state import TMState
from app.core.llm import get_solar_pro_chat_client
from app.core.logger import logger

def keyword_extraction_node(state: TMState) -> dict:
    """
    CSV 파일의 'title' 컬럼을 기반으로 LLM을 사용하여 트렌드 키워드를 추출하고,
    결과를 새로운 CSV 파일로 저장하는 전체 프로세스를 수행합니다.
    """
    logger.info("--- (KE) Entered Keyword Extraction Subgraph ---")
    try:
        # 1. CSV 읽기
        logger.info("Step KE.1: Loading data from CSV...")
        csv_path = state.get("csv_path")
        if not csv_path or not csv_path.endswith('.csv'):
            return {"error": "Invalid or missing CSV file path."}

        df = pd.read_csv(csv_path)
        if 'title' not in df.columns:
            return {"error": "'title' column not found in the CSV."}
        logger.info(f"Successfully loaded {len(df)} rows from {csv_path}")

        # 2. 키워드 추출
        logger.info("Step KE.2: Starting trend keyword extraction via LLM...")
        df_processed = df.copy()
        client = get_solar_pro_chat_client()
        model_name = "solar-pro"
        batch_size = 50
        titles = df_processed['title'].tolist()
        all_keywords = []

        def extract_trend_keywords(titles_batch):
            system_prompt = """
            당신은 '유튜브 바이럴 트렌드 분석가'입니다.
            제공된 제목에서 마케팅에 활용할 수 있는 **'핵심 트렌드 키워드'**를 추출하세요.
            [추출 원칙]
            1. **구체적인 아이템/신조어 우선**: '쿠키'보다는 '두바이 쫀득쿠키', '아이스크림'보다는 '요아정'과 같이 고유명사나 유행하는 복합명사를 그대로 추출하세요.
            2. **불필요한 단어 제거**: '브이로그', '추천', '영상', '리뷰', 'ㅋㅋㅋ', '존맛' 같은 일반적인 수식어나 감탄사는 제외하세요.
            3. **맥락 파악**: 제목이 특정 챌린지나 밈(Meme)을 다룬다면 해당 밈의 이름을 정확히 추출하세요 (예: '꽁꽁 얼어붙은 한강').
            [출력 형식]
            반드시 JSON 형식으로 반환하세요:
            { "results": [ {"title": "원본 제목", "keywords": ["키워드1", "키워드2"]} ] }
            """
            user_prompt = f"아래 제목 리스트를 분석하여 JSON으로 출력해줘.\n\n[제목 리스트]\n{json.dumps(titles_batch, ensure_ascii=False)}"
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"}
                )
                return json.loads(response.choices[0].message.content).get('results', [])
            except Exception as api_e:
                logger.error(f"Upstage API Error: {api_e}")
                return []

        for i in tqdm(range(0, len(titles), batch_size)):
            batch_titles = titles[i : i + batch_size]
            results = extract_trend_keywords(batch_titles)
            title_to_keywords = {item.get('title'): item.get('keywords', []) for item in results}
            for t in batch_titles:
                keywords = title_to_keywords.get(t, [])
                all_keywords.append(", ".join(keywords))

        if len(all_keywords) < len(titles):
            all_keywords.extend([""] * (len(titles) - len(all_keywords)))
        df_processed['trend_keywords'] = all_keywords[:len(df_processed)]
        logger.info("Keyword extraction via LLM complete.")

        # 3. CSV 저장
        logger.info("Step KE.3: Saving results to new CSV file...")
        output_path = csv_path.replace(".csv", "_with_keywords.csv")
        df_processed.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"Analysis complete! Saved to '{output_path}'")
        logger.info("\n--- Preview of Results ---\n" + df_processed[['title', 'trend_keywords']].head().to_string())
        logger.info("--- Keyword Extraction Subgraph Finished ---")

        return {"output_path": output_path, "error": None}

    except Exception as e:
        logger.error(f"An error occurred in the keyword extraction process: {e}", exc_info=True)
        return {"error": str(e)}

# --- 그래프 구성 (다른 서브그래프와 동일한 구조) ---
workflow = StateGraph(TMState)
workflow.add_node("keyword_extraction", keyword_extraction_node)
workflow.set_entry_point("keyword_extraction")
workflow.add_edge("keyword_extraction", END)
keyword_extraction_graph = workflow.compile()
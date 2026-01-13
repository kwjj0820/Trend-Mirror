# app/agents/subgraphs/keyword_extract.py
import pandas as pd
import json
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from tqdm import tqdm

from app.agents.state import TMState
from app.core.llm import get_solar_pro_chat_client
from app.core.logger import logger

def keyword_extraction_node(state: TMState, config: RunnableConfig) -> dict:
    """
    CSV 파일의 'title'과 'description' 컬럼을 기반으로, 지정된 '도메인'에 맞는
    트렌드 키워드를 LLM을 사용하여 추출하고, 결과를 새로운 CSV 파일로 저장합니다.
    """
    logger.info("--- (KE) Entered Keyword Extraction Subgraph ---")
    try:
        # 1. CSV 및 도메인 정보 읽기
        logger.info("Step KE.1: Loading data and domain from state...")
        csv_path = state.get("csv_path")
        domain = state.get("slots", {}).get("goal", "any") # 도메인이 없으면 'any'

        if not csv_path or not csv_path.endswith('.csv'):
            return {"error": "Invalid or missing CSV file path."}

        df = pd.read_csv(csv_path)
        # 제목과 설명 컬럼이 모두 있는지 확인
        if 'title' not in df.columns or 'description' not in df.columns:
            return {"error": "'title' and/or 'description' column not found in the CSV."}
        
        # 설명이 없는 경우를 대비해 빈 문자열로 채움
        df['description'] = df['description'].fillna('')
        
        logger.info(f"Successfully loaded {len(df)} rows. Domain set to '{domain}'.")

        # 2. 키워드 추출
        logger.info("Step KE.2: Starting domain-specific trend keyword extraction via LLM...")
        df_processed = df.copy()
        client = get_solar_pro_chat_client()
        model_name = "solar-pro"
        batch_size = 20 # 컨텍스트가 길어졌으므로 배치 크기 축소
        
        videos_info = df_processed[['title', 'description']].to_dict('records')
        all_keywords = []

        def extract_trend_keywords(videos_batch, domain_filter):
            system_prompt = f"""
            당신은 '{domain_filter}' 도메인의 '유튜브 바이럴 트렌드 분석가'입니다.
            제공된 영상 정보(제목과 설명)에서 마케팅에 활용할 수 있는 **'{domain_filter}'과(와) 관련된 핵심 트렌드 키워드**만 추출하세요.
            
            [추출 원칙]
            1. **도메인 관련성**: 반드시 '{domain_filter}'와 직접적으로 관련된 키워드만 추출하세요. 관련 없으면 추출하지 마세요.
            2. **구체적인 아이템/신조어 우선**: '쿠키'보다는 '두바이 쫀득쿠키', '아이스크림'보다는 '요아정'과 같이 고유명사나 유행하는 복합명사를 그대로 추출하세요.
            3. **불필요한 단어 제거**: '브이로그', '추천', '영상', '리뷰', 'ㅋㅋㅋ', '존맛' 같은 일반적인 수식어나 감탄사는 제외하세요.
            4. **맥락 파악**: 제목이나 설명이 특정 챌린지나 밈(Meme)을 다룬다면 해당 밈의 이름을 정확히 추출하세요 (예: '꽁꽁 얼어붙은 한강').

            [출력 형식]
            반드시 JSON 형식으로 반환하세요:
            {{ "results": [ {{"title": "원본 제목", "keywords": ["키워드1", "키워드2"]}} ] }}
            """
            user_prompt = f"아래 영상 정보 리스트를 분석하여 JSON으로 출력해줘.\n\n[영상 정보 리스트]\n{json.dumps(videos_batch, ensure_ascii=False)}"
            
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

        for i in tqdm(range(0, len(videos_info), batch_size)):
            batch_info = videos_info[i : i + batch_size]
            results = extract_trend_keywords(batch_info, domain)
            
            title_to_keywords = {item.get('title'): item.get('keywords', []) for item in results}
            
            for info in batch_info:
                original_title = info['title']
                keywords = title_to_keywords.get(original_title, [])
                all_keywords.append(", ".join(keywords))

        if len(all_keywords) < len(df_processed):
            all_keywords.extend([""] * (len(df_processed) - len(all_keywords)))
        df_processed['trend_keywords'] = all_keywords[:len(df_processed)]
        logger.info("Keyword extraction via LLM complete.")

        # 3. CSV 저장 및 DB 동기화
        logger.info("Step KE.3: Saving results to new CSV file...")
        output_path = csv_path.replace(".csv", "_with_keywords.csv")
        df_processed.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        sync_service = config["configurable"].get("sync_service")
        if sync_service:
            logger.info("Step KE.4: Syncing extracted keywords to Vector DB...")
            try:
                sync_service.sync_csv_to_db(output_path)
            except Exception as sync_e:
                logger.error(f"Failed to sync data to DB: {sync_e}", exc_info=True)
        else:
            logger.warning("SyncService not found in config. Skipping DB sync.")

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
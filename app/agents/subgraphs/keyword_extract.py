import pandas as pd
import json
import time
import os
from io import StringIO
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from tqdm import tqdm

from app.agents.state import TMState
from app.core.llm import get_solar_pro_chat_client
from app.core.logger import logger
from app.service.vector_service import VectorService

def keyword_extraction_node(state: TMState, config: RunnableConfig) -> dict:
    """
    LLM을 사용하여 트렌드 키워드를 추출하고, 결과를 벡터 DB에 동기화합니다.
    안정성을 위해 배치 사이즈를 줄이고 API 타임아웃을 설정했습니다.
    """
    logger.info("--- (KE) Entered Keyword Extraction Subgraph ---")
    
    # 벡터 서비스 및 설정 로드
    vector_service: VectorService = config["configurable"].get("vector_service")
    
    try:
        # 1. 데이터 로드 (input_df_json으로부터)
        input_df_json = state.get("input_df_json")
        base_export_path = state.get("base_export_path")
        slots = state.get("slots", {})
        domain = slots.get("domain", "any")
        category = slots.get("search_query", domain)

        if not input_df_json or not base_export_path:
            return {"error": "필수 데이터(JSON 또는 export 경로)가 누락되었습니다."}

        df = pd.read_json(StringIO(input_df_json), orient='split')
        logger.info(f"KE Node: 총 {len(df)}개의 데이터를 처리합니다. (도메인: {domain})")

        # 2. 키워드 추출 설정
        model_name = "solar-pro"
        batch_size = 10 
        client = get_solar_pro_chat_client()
        
        videos_info = df[['title', 'description']].fillna('').to_dict('records')
        all_keywords = []

        def extract_trend_keywords(videos_batch, domain_filter):
            system_prompt = f"""
            당신은 '{domain_filter}' 도메인의 분석가입니다. 영상 정보에서 마케팅 트렌드 키워드를 추출하세요.
            반드시 JSON 형식으로 반환하세요:
            {{ "results": [ {{"title": "원본 제목", "keywords": ["키워드1", "키워드2"]}} ] }}
            """
            user_prompt = f"아래 리스트를 분석해줘:\n{json.dumps(videos_batch, ensure_ascii=False)}"
            
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                    timeout=120 
                )
                return json.loads(response.choices[0].message.content).get('results', [])
            except Exception as e:
                logger.error(f"API 호출 중 오류 발생 (배치 건너뜀): {e}")
                return []

        # 3. 루프 실행 (Progress Bar)
        for i in tqdm(range(0, len(videos_info), batch_size)):
            batch_info = videos_info[i : i + batch_size]
            results = extract_trend_keywords(batch_info, domain)
            
            title_to_keywords = {item.get('title'): item.get('keywords', []) for item in results}
            for info in batch_info:
                keywords = title_to_keywords.get(info['title'], [])
                all_keywords.append(", ".join(keywords))
            
            time.sleep(0.5)

        # 결과 병합
        df_processed = df.copy()
        df_processed['trend_keywords'] = all_keywords[:len(df_processed)]

        # 4. CSV 저장 및 벡터 DB 동기화
        output_path = f"{base_export_path}_with_keywords.csv"
        # 파일 저장 전 디렉토리 존재 확인 및 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_processed.to_csv(output_path, index=False, encoding='utf-8-sig')

        if vector_service and not df_processed.empty:
            documents = []
            metadatas = []
            ids = []

            for idx, row in df_processed.iterrows():
                text_content = f"제목: {row['title']}\n내용: {row['description']}\n키워드: {row['trend_keywords']}"
                documents.append(text_content)
                metadatas.append({
                    "keyword": row['trend_keywords'],
                    "category": category,
                    "sns": "youtube",
                    "published_at": str(row.get('published_at', ''))
                })
                ids.append(f"yt_{row.get('video_id', idx)}")

            vector_service.add_documents(documents=documents, metadatas=metadatas, ids=ids)
            logger.info(f"벡터 DB에 {len(documents)}건의 데이터를 동기화했습니다.")

        # 5. 빈도수 계산 및 반환
        all_extracted_keywords = []
        for keywords_str in df_processed['trend_keywords'].dropna():
            keywords_in_row = [kw.strip().replace(' ', '') for kw in keywords_str.split(',') if kw.strip()]
            all_extracted_keywords.extend(list(set(keywords_in_row)))
        
        from collections import Counter
        keyword_counts = Counter(all_extracted_keywords)
        df_frequencies = pd.DataFrame(keyword_counts.items(), columns=['keyword', 'frequency'])
        df_frequencies = df_frequencies.sort_values(by='frequency', ascending=False)

        return {
            "frequencies_df_json": df_frequencies.to_json(orient='split', index=False),
            "output_path": output_path,
            "error": None
        }

    except Exception as e:
        logger.error(f"KE Node 전체 오류: {e}", exc_info=True)
        return {"error": str(e)}

# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("keyword_extraction", keyword_extraction_node)
workflow.set_entry_point("keyword_extraction")
workflow.add_edge("keyword_extraction", END)
keyword_extraction_graph = workflow.compile()
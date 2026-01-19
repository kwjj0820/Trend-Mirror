import pandas as pd
import json
import time
import os
from datetime import datetime
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
    logger.info("--- (KE) v2 --- Keyword Extraction Code ACTIVE ---") # New test log
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
        batch_size = 50
        client = get_solar_pro_chat_client()
        
        videos_info = df[['title', 'description']].fillna('').to_dict('records')
        all_keywords = []
        all_sentiments = [] # 감성 분석 결과 저장

        def extract_trend_keywords(videos_batch, domain_filter):
            system_prompt = f"""
            당신은 '{domain_filter}' 도메인의 전문 분석가입니다. 영상 정보에서 마케팅 트렌드 키워드를 추출하고, 각 영상의 긍정/부정/중립 감성을 분석하는 것이 당신의 임무입니다.

            **키워드 추출에 대한 핵심 지침:**
            1.  **핵심 키워드 식별**: 모든 관련 트렌드 키워드를 추출하세요.
            2.  **동의어 및 변형 정규화**:
                - **의미 기반 통합**: 동일한 개념에 대한 여러 변형, 약어 또는 동의어를 찾으면, 반드시 가장 대표적인 단일 키워드로 통합해야 합니다.
                - **공백/특수문자 무시**: 띄어쓰기 유무나 사소한 특수문자 차이도 같은 키워드로 취급해야 합니다. (예: "두바이쫀득쿠키"와 "두바이 쫀득쿠키"는 동일)
            3.  **노이즈 필터링**: 일반적이거나 트렌드와 관련 없는 용어는 제외하세요.

            **출력 형식:**
            결과는 엄격한 JSON 형식으로 반환하세요. 모든 변형이 당신이 선택한 단일 정규화된 키워드에 매핑되었는지 확인하세요.

            {{
                "results": [
                    {{
                        "title": "원본 영상 제목",
                        "keywords": ["정규화된 키워드 1", "정규화된 키워드 2"],
                        "sentiment": "positive" | "negative" | "neutral"
                    }}
                ]
            }}

            **올바른 정규화 예시:**
            - **예시 1 (약어 통합)**: 텍스트에 "두쫀쿠 인기"와 "두바이 쫀득쿠키 후기"가 포함되어 있다면, 출력 키워드는 "두바이 쫀득쿠키" 하나여야 합니다.
            - **예시 2 (띄어쓰기 통합)**: 텍스트에 "얼그레이하이볼"과 "얼그레이 하이볼"이 있다면, 출력 키워드는 "얼그레이 하이볼" 하나여야 합니다.

            이제 아래 리스트를 분석해주세요:
            """
            user_prompt = f"아래 리스트를 분석해줘:\n{json.dumps(videos_batch, ensure_ascii=False)}"
            
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                    timeout=120 
                )
                response_content = response.choices[0].message.content
                logger.debug(f"LLM raw response content: {response_content}")
                
                response_data = json.loads(response_content)
                results = response_data.get('results', [])
                
                if not results:
                    logger.warning("LLM returned no 'results' or an empty 'results' list.")

                return results
            except Exception as e:
                logger.error(f"API 호출 중 오류 발생 (배치 건너뜀): {e}", exc_info=True)
                return []

        # 3. 루프 실행 (Progress Bar)
        for i in tqdm(range(0, len(videos_info), batch_size)):
            batch_info = videos_info[i : i + batch_size]
            results = extract_trend_keywords(batch_info, domain)
            
            title_to_data = {item.get('title'): {
                'keywords': item.get('keywords', []),
                'sentiment': item.get('sentiment', 'neutral')
            } for item in results}

            for info in batch_info:
                data = title_to_data.get(info['title'], {'keywords': [], 'sentiment': 'neutral'})
                all_keywords.append(", ".join(data['keywords']))
                all_sentiments.append(data['sentiment'])
            
            time.sleep(0.5)

        # 결과 병합
        df_processed = df.copy()
        df_processed['trend_keywords'] = all_keywords[:len(df_processed)]
        df_processed['sentiment'] = all_sentiments[:len(df_processed)]

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
                # `published_at`을 Unix 타임스탬프로 변환 (더 강력한 방식)
                pub_date_val = row.get('published_at')
                if pd.isna(pub_date_val):
                    timestamp = datetime.now().timestamp()
                else:
                    try:
                        # to_datetime은 다양한 포맷을 처리할 수 있음
                        timestamp = pd.to_datetime(pub_date_val).timestamp()
                    except (ValueError, TypeError):
                        timestamp = datetime.now().timestamp()
                
                metadatas.append({
                    "keyword": row['trend_keywords'],
                    "category": category,
                    "sns": "youtube",
                    "sentiment": row['sentiment'],
                    "published_at": timestamp
                })
                ids.append(f"yt_{row.get('video_id', idx)}")

            vector_service.add_documents(documents=documents, metadatas=metadatas, ids=ids)
            logger.info(f"Adding documents to vector DB. Sample metadatas (first 3): {metadatas[:3]}") # Log metadatas for verification
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

        # 감성 빈도수 계산
        sentiment_counts = Counter(df_processed['sentiment'].dropna())
        df_sentiment_frequencies = pd.DataFrame(sentiment_counts.items(), columns=['sentiment', 'frequency'])
        df_sentiment_frequencies = df_sentiment_frequencies.sort_values(by='frequency', ascending=False)

        return {
            "frequencies_df_json": df_frequencies.to_json(orient='split', index=False),
            "sentiment_frequencies_df_json": df_sentiment_frequencies.to_json(orient='split', index=False), # 감성 빈도수 추가
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
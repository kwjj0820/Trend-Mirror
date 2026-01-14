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
        slots = state.get("slots", {})
        domain = slots.get("domain", "any") # 도메인이 없으면 'any'

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
        model_name = "solar-pro"
        batch_size = 20 # 컨텍스트가 길어졌으므로 배치 크기 축소
        logger.info(f"Step KE.2: Starting domain-specific trend keyword extraction via LLM with batch_size={batch_size}...")
        df_processed = df.copy()
        client = get_solar_pro_chat_client()
        
        videos_info = df_processed[['title', 'description']].to_dict('records')
        all_keywords = []

        def extract_trend_keywords(videos_batch, domain_filter):
            system_prompt = f"""
            당신은 '{domain_filter}' 도메인의 '유튜브 바이럴 트렌드 분석가'입니다.
            제공된 영상 정보(제목과 설명)에서 마케팅에 활용할 수 있는 **'{domain_filter}'과(와) 관련된 트렌드 키워드**를 추출하세요.
            '관련된'의 의미는 영상이 직접적으로 '{domain_filter}'에 대한 것이 아니더라도, '{domain_filter}'을 이해하고 트렌드를 분석하는 데 도움이 되는 키워드를 포함합니다.

            [추출 원칙]
            1. **트렌드 키워드 우선**: 영상에서 언급된 내용 중 현재 유행하거나 주목받는 키워드를 찾아 추출하세요.
            2. **구체적인 아이템/신조어 우선**: '쿠키'보다는 '두바이 쫀득쿠키', '아이스크림'보다는 '요아정'과 같이 고유명사나 유행하는 복합명사를 그대로 추출하세요.
            3. **불필요한 단어 제거**: '브이로그', '추천', '영상', '리뷰', 'ㅋㅋㅋ', '존맛' 같은 일반적인 수식어나 감탄사는 제외하세요.
            4. **맥락 파악**: 제목이나 설명이 특정 챌린지나 밈(Meme)을 다룬다면 해당 밈의 이름을 정확히 추출하세요 (예: '꽁꽁 얼어붙은 한강').

            [상위 개념 추출 원칙]
            1. **카테고리화**: 여러 개의 구체적인 키워드가 하나의 상위 카테고리(예: 게임, 영화, 브랜드, 특정 음식 종류)에 속할 경우, 해당 상위 카테고리 이름도 키워드로 함께 추출하세요.
                - **예시 1**: 영상에서 '테란', '저그'와 같은 키워드가 발견되면, '스타크래프트'도 키워드로 추가하세요.
                - **예시 2**: '다리우스', '페이커' 같은 단어가 나오면 '리그오브레전드'를 추가하세요.
                - **예시 3**: '로제떡볶이', '마라떡볶이'가 나오면 '떡볶이'를 추가하여 더 넓은 트렌드를 파악할 수 있도록 하세요.
            2. **목적**: 이 원칙은 개별 아이템뿐만 아니라, 그 아이템들이 형성하는 더 큰 트렌드나 맥락을 포착하기 위함입니다.

            [키워드 정규화 원칙]
            1. **표준 형태로 통일 (Normalization)**: 의미적으로 동일한 대상에 대한 다양한 표현을 **가장 대표적인 한글 명칭**으로 통일하세요.
                - **축약어 -> 원형**: '두쫀쿠'는 '두바이쫀득쿠키'로 변환하세요.
                - **오타 수정**: '두바이쫀듯쿠키'와 같은 명백한 오타는 '두바이쫀득쿠키'로 교정하세요.
                - **외래어/외국어 표기 통일**: 'tanghulu'나 다른 표기는 '탕후루'로 통일하세요.
            2. **띄어쓰기 제거**: 최종 키워드에서는 모든 띄어쓰기를 제거하세요. (예: '두바이 쫀득 쿠키'는 '두바이쫀득쿠키'가 되어야 합니다.)
            3. **최종 일관성**: 위의 원칙에 따라, '두쫀쿠', '두바이 쫀득 쿠키', '두바이쫀듯쿠키' 등은 모두 '두바이쫀득쿠키'라는 단 하나의 키워드로 출력되어야 합니다.

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
                parsed_results = json.loads(response.choices[0].message.content).get('results', [])
                return parsed_results
            except Exception as api_e:
                logger.error(f"Upstage API Error during keyword extraction: {api_e}")
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
        logger.info(f"Keyword-extracted data saved to '{output_path}'")

        # 키워드 빈도수 카운팅 및 CSV 저장
        all_extracted_keywords = []
        for keywords_str in df_processed['trend_keywords'].dropna():
            # 한 행(영상) 내에서 중복된 키워드는 한 번만 카운트하기 위해 set으로 변환 후 추가
            keywords_in_row = [kw.strip().replace(' ', '') for kw in keywords_str.split(',') if kw.strip()]
            unique_keywords_in_row = set(keywords_in_row)
            all_extracted_keywords.extend(list(unique_keywords_in_row))
        
        from collections import Counter
        keyword_counts = Counter(all_extracted_keywords)
        
        df_frequencies = pd.DataFrame(keyword_counts.items(), columns=['keyword', 'frequency'])
        df_frequencies = df_frequencies.sort_values(by='frequency', ascending=False)
        
        freq_output_path = csv_path.replace(".csv", "_keyword_frequencies.csv")
        df_frequencies.to_csv(freq_output_path, index=False, encoding='utf-8-sig')
        logger.info(f"Keyword frequencies saved to '{freq_output_path}'")
        
        # ⚠️ 중요: Step KE.4 수정 - freq_output_path를 동기화에 사용
        sync_service = config["configurable"].get("sync_service")
        if sync_service:
            logger.info("Step KE.4: Syncing extracted keywords to Vector DB...")
            try:
                # 수정된 부분: output_path 대신 freq_output_path 전달
                sync_service.sync_csv_to_db(freq_output_path)
            except Exception as sync_e:
                logger.error(f"Failed to sync data to DB: {sync_e}", exc_info=True)
        else:
            logger.warning("SyncService not found in config. Skipping DB sync.")

        logger.info(f"Analysis complete! Saved to '{output_path}'")
        logger.info("--- Keyword Extraction Subgraph Finished ---")

        return {"output_path": output_path, "error": None}

    except Exception as e:
        logger.error(f"An error occurred in the keyword extraction process: {e}", exc_info=True)
        return {"error": str(e)}

# --- 그래프 구성 ---
workflow = StateGraph(TMState)
workflow.add_node("keyword_extraction", keyword_extraction_node)
workflow.set_entry_point("keyword_extraction")
workflow.add_edge("keyword_extraction", END)
keyword_extraction_graph = workflow.compile()
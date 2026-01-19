import pandas as pd
import datetime
import os
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from app.agents.state import TMState
from app.core.logger import logger
from app.service.vector_service import VectorService
from app.agents.tools import generate_report_pdf_v2_tool

# 1. Matplotlib 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 2. 시각화 헬퍼 함수들 (이미지 저장 기능 포함)
def save_plot(fig, filename, plot_type):
    """Matplotlib Figure를 이미지 파일로 저장"""
    image_dir = os.path.join("reports", "images")
    os.makedirs(image_dir, exist_ok=True)
    filepath = os.path.join(image_dir, f"{filename}_{plot_type}.png")
    fig.savefig(filepath, bbox_inches='tight', dpi=150)
    plt.close(fig)
    return filepath

def plot_keyword_pie_chart(data, title, filename):
    """키워드 언급량 원형 그래프를 생성하고 파일로 저장합니다."""
    if not data: return None
    df = pd.DataFrame(data)
    if df.empty or 'frequency' not in df.columns or 'keyword' not in df.columns:
        return None
    fig, ax = plt.subplots(figsize=(10, 8))
    labels = df['keyword']
    sizes = df['frequency']
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, textprops={'fontsize': 10})
    ax.axis('equal')
    ax.set_title(title, fontsize=16, pad=20)
    return save_plot(fig, filename, 'keyword_pie')

def plot_daily_sentiment_bar_chart(df_pivot, title, filename):
    """일별 감성 분석 누적 막대 그래프를 생성하고 파일로 저장합니다."""
    if df_pivot.sum().sum() == 0:
        logger.warning("plot_daily_sentiment_bar_chart: All sentiment counts are zero. Skipping plot generation.")
        return None
    
    color_map = {'positive': '#2ecc71', 'neutral': '#95a5a6', 'negative': '#e74c3c'}
    colors = [color_map.get(col, '#333333') for col in df_pivot.columns]

    fig, ax = plt.subplots(figsize=(10, 6))
    df_pivot.plot(kind='bar', stacked=True, ax=ax, color=colors)

    ax.set_title(title, fontsize=16, pad=15)
    ax.set_xlabel('날짜', fontsize=12)
    ax.set_ylabel('언급 빈도', fontsize=12)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend(title='Sentiment')

    return save_plot(fig, filename, 'daily_sentiment_bar')

def get_daily_sentiment_pivot_table(docs: list, start_date: datetime.datetime, end_date: datetime.datetime):
    """원시 문서를 피벗 테이블 DataFrame으로 처리합니다."""
    if not docs:
        return pd.DataFrame()

    sentiment_records = []
    for doc in docs:
        ts = doc.get("published_at")
        sentiment = doc.get("sentiment")
        if ts and sentiment:
            try:
                dt = datetime.datetime.fromtimestamp(float(ts))
                sentiment_records.append({'date': pd.Timestamp(dt).normalize(), 'sentiment': sentiment})
            except (ValueError, TypeError):
                continue
    
    if not sentiment_records:
        return pd.DataFrame()

    df = pd.DataFrame(sentiment_records)
    df_pivot = df.groupby(['date', 'sentiment']).size().unstack(fill_value=0)

    for s in ['positive', 'neutral', 'negative']:
        if s not in df_pivot.columns:
            df_pivot[s] = 0
    
    full_date_range = pd.date_range(start=start_date, end=end_date, freq='D').normalize()
    df_pivot = df_pivot.reindex(full_date_range, fill_value=0)
    df_pivot = df_pivot[['positive', 'neutral', 'negative']]
    
    return df_pivot

# 메인 노드
def visualization_gen_node(state: TMState, config: RunnableConfig):
    """
    데이터를 처리하여 Streamlit용 데이터와 PDF용 이미지를 모두 생성합니다.
    """
    logger.info("--- [5] Visualization Generation Node (Dual Output) ---")
    
    vector_service: VectorService = config["configurable"].get("vector_service")
    slots = state.get("slots", {})
    report_text = state.get("report_text", "리포트 내용이 없습니다.")
    
    category = slots.get('search_query', "report")
    period_days = slots.get("period_days", 7)
    sns_channel = "youtube"

    end_date_dt = datetime.datetime.now()
    start_date_dt = end_date_dt - datetime.timedelta(days=period_days)
    start_date_str = start_date_dt.strftime("%Y-%m-%d")
    end_date_str = end_date_dt.strftime("%Y-%m-%d")
    base_filename = f"{ ''.join(c for c in category if c.isalnum()) }_{period_days}d"
    
    # --- 데이터 조회 및 처리 ---
    keyword_freq_data = vector_service.get_keyword_frequencies(
        category=category, sns=sns_channel, n_results=10,
        start_date=start_date_str, end_date=end_date_str
    )
    all_docs = vector_service.get_documents_for_period(
        category=category, sns=sns_channel,
        start_date=start_date_str, end_date=end_date_str
    )
    sentiment_pivot_df = get_daily_sentiment_pivot_table(all_docs, start_date_dt, end_date_dt)

    # --- 1. Streamlit용 데이터 준비 ---
    daily_sentiments_data = sentiment_pivot_df.reset_index().rename(columns={'index': 'date'})
    daily_sentiments_data['date'] = daily_sentiments_data['date'].dt.strftime('%Y-%m-%d')
    daily_sentiments_for_frontend = daily_sentiments_data.to_dict('records')
    logger.info(f"Prepared {len(keyword_freq_data)} keyword frequencies for Streamlit.")
    logger.info(f"Processed {len(daily_sentiments_for_frontend)} days of sentiment data for Streamlit.")

    # --- 2. PDF용 이미지 생성 ---
    image_paths = []
    pie_path = plot_keyword_pie_chart(keyword_freq_data, f'키워드 언급 비중 ({category})', base_filename)
    if pie_path: 
        image_paths.append(pie_path)
        logger.info(f"Generated pie chart image: {pie_path}")

    # Pivot 테이블의 인덱스(날짜)를 x축 레이블로 사용하기 위해 문자열로 변환
    sentiment_pivot_df_for_plot = sentiment_pivot_df.copy()
    sentiment_pivot_df_for_plot.index = sentiment_pivot_df_for_plot.index.strftime('%Y-%m-%d')
    sentiment_bar_path = plot_daily_sentiment_bar_chart(sentiment_pivot_df_for_plot, '일별 감성 추이', base_filename)
    if sentiment_bar_path: 
        image_paths.append(sentiment_bar_path)
        logger.info(f"Generated sentiment bar chart image: {sentiment_bar_path}")

    # --- 3. PDF 생성 ---
    pdf_content = report_text
    if image_paths:
        pdf_content += "\n\n---\n\n## 생성된 시각화 자료\n"
        for img_path in image_paths:
            # Markdown 이미지 링크 형식으로 변환
            pdf_content += f"![{os.path.basename(img_path)}]({os.path.abspath(img_path)})\n"

    pdf_filename = f"{base_filename}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = generate_report_pdf_v2_tool.invoke({"content": pdf_content, "filename": pdf_filename})
    logger.info(f"PDF Generation Complete. PDF saved at: {pdf_path}")

    # --- 4. 최종 결과 반환 ---
    return {
        "final_answer": report_text,
        "pdf_path": str(pdf_path),
        "keyword_frequencies": keyword_freq_data,
        "daily_sentiments": daily_sentiments_for_frontend,
        "image_paths": [str(p) for p in image_paths] 
    }

# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("visualization_gen", visualization_gen_node)
workflow.set_entry_point("visualization_gen")
workflow.add_edge("visualization_gen", END)
visualization_graph = workflow.compile()
# app/agents/subgraphs/visualization_gen.py
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from app.agents.state import TMState
from app.core.logger import logger
from app.service.vector_service import VectorService
import datetime
import os

# 1. Matplotlib 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 2. 시각화 헬퍼 함수들
def save_plot(fig, filename, plot_type):
    """Matplotlib Figure를 이미지 파일로 저장"""
    image_dir = os.path.join("reports", "images")
    os.makedirs(image_dir, exist_ok=True)
    filepath = os.path.join(image_dir, f"{filename}_{plot_type}.png")
    fig.savefig(filepath, bbox_inches='tight', dpi=150)
    plt.close(fig)
    return filepath

def plot_keyword_pie_chart(data, title, filename):
    """키워드 언급량 원형 그래프 생성"""
    if not data: return None
    df = pd.DataFrame(data)
    if df.empty or 'frequency' not in df.columns or 'keyword' not in df.columns:
        logger.warning("Pie chart cannot be generated due to missing data or columns.")
        return None
    fig, ax = plt.subplots(figsize=(10, 8))
    labels = df['keyword']
    sizes = df['frequency']
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, textprops={'fontsize': 10})
    ax.axis('equal')
    ax.set_title(title, fontsize=16, pad=20)
    return save_plot(fig, filename, 'keyword_pie')

def plot_daily_sentiment_bar_chart(docs, title, filename, start_date, end_date):
    """일별 감성 분석 누적 막대 그래프 생성"""
    if not docs: return None
    
    sentiment_records = []
    for doc in docs:
        ts = doc.get("published_at")
        sentiment = doc.get("sentiment")
        if ts and sentiment:
            try:
                sentiment_records.append({
                    'date': datetime.datetime.fromtimestamp(float(ts)).date(),
                    'sentiment': sentiment
                })
            except (ValueError, TypeError):
                continue
    
    if not sentiment_records: return None
    
    df = pd.DataFrame(sentiment_records)
    df_pivot = df.groupby(['date', 'sentiment']).size().unstack(fill_value=0)
    
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    df_pivot = df_pivot.reindex(date_range, fill_value=0)

    fig, ax = plt.subplots(figsize=(12, 7))
    df_pivot.plot(kind='bar', stacked=True, ax=ax, colormap='viridis')
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Date')
    ax.set_ylabel('Frequency')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(axis='y', linestyle='--')
    
    return save_plot(fig, filename, 'daily_sentiment_bar')

def plot_radar_chart(data, title, filename):
    """레이더 차트 생성"""
    if not data or len(data) < 3: return None # 레이더 차트는 최소 3개의 축이 필요
    
    labels = list(data.keys())
    stats = list(data.values())
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats = np.concatenate((stats,[stats[0]]))
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, stats, color='blue', linewidth=2)
    ax.fill(angles, stats, color='blue', alpha=0.25)
    
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=12)
    ax.set_title(title, size=15, pad=20)
    
    return save_plot(fig, filename, 'radar')

def plot_positioning_map(data, title, filename):
    """포지셔닝 맵 (스캐터 플롯) 생성"""
    if not data: return None
    
    records = []
    for keyword, metrics in data.items():
        if 'position_scores' in metrics:
            records.append({
                'keyword': keyword,
                'viability': metrics['position_scores'].get('viability', 0),
                'opportunity': metrics['position_scores'].get('opportunity', 0)
            })

    if not records: return None
    df = pd.DataFrame(records)

    fig, ax = plt.subplots(figsize=(10, 10))
    sns.scatterplot(x='viability', y='opportunity', data=df, s=200, ax=ax, hue='keyword', legend=False, palette='viridis')

    for i, row in df.iterrows():
        ax.text(row['viability'] + 0.1, row['opportunity'] + 0.1, row['keyword'], fontsize=12)

    ax.axhline(5, color='gray', linestyle='--')
    ax.axvline(5, color='gray', linestyle='--')
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 11)
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Trend Viability (안정성/성숙도)', fontsize=12)
    ax.set_ylabel('Opportunity (기회/수익성)', fontsize=12)

    ax.text(10.5, 10.5, '현재 유효, 리턴 큼', ha='right', va='top', fontsize=12, color='green', alpha=0.7)
    ax.text(0.5, 0.5, '리스크 크고 이윤 적음', ha='left', va='bottom', fontsize=12, color='red', alpha=0.7)
    
    return save_plot(fig, filename, 'positioning_map')

# 4. 메인 노드
def visualization_gen_node(state: TMState, config: RunnableConfig):
    """
    분석된 데이터를 바탕으로 모든 시각화 자료를 생성하고 PDF 리포트를 조립합니다.
    """
    logger.info("--- [5] Visualization Generation Node ---")
    
    vector_service: VectorService = config["configurable"].get("vector_service")
    slots = state.get("slots", {})
    report_text = state.get("report_text", "리포트 내용이 없습니다.")
    analysis_metrics = state.get("analysis_metrics", {})
    
    category = slots.get('search_query', "report")
    period_days = slots.get("period_days", 7)
    sns_channel = "youtube"

    end_date_dt = datetime.datetime.now()
    start_date_dt = end_date_dt - datetime.timedelta(days=period_days)
    start_date_str = start_date_dt.strftime("%Y-%m-%d")
    end_date_str = end_date_dt.strftime("%Y-%m-%d")
    
    image_paths = []
    base_filename = f"{''.join(c for c in category if c.isalnum())}_{period_days}d"
    
    # --- 데이터 조회 ---
    keyword_freq_data = vector_service.get_keyword_frequencies(
        category=category, sns=sns_channel, n_results=10,
        start_date=start_date_str, end_date=end_date_str
    )
    all_docs = vector_service.get_documents_for_period(
        category=category, sns=sns_channel,
        start_date=start_date_str, end_date=end_date_str
    )
    
    pie_path = plot_keyword_pie_chart(keyword_freq_data, f'키워드 언급 비중 ({category})', base_filename)
    if pie_path: image_paths.append(pie_path); logger.info(f"Generated pie chart: {pie_path}")

    sentiment_bar_path = plot_daily_sentiment_bar_chart(all_docs, '일별 감성 추이', base_filename, start_date_dt, end_date_dt)
    if sentiment_bar_path: image_paths.append(sentiment_bar_path); logger.info(f"Generated sentiment bar chart: {sentiment_bar_path}")
    
    if analysis_metrics:
        for kw, metrics in analysis_metrics.items():
            radar_scores = metrics.get('radar_scores')
            if radar_scores:
                kw_filename = f"{base_filename}_{''.join(c for c in kw if c.isalnum())}"
                radar_path = plot_radar_chart(radar_scores, f'"{kw}" 키워드 요소 분석', kw_filename)
                if radar_path: image_paths.append(radar_path); logger.info(f"Generated radar chart for {kw}: {radar_path}")
        
        pos_map_path = plot_positioning_map(analysis_metrics, '키워드 포지셔닝 맵', base_filename)
        if pos_map_path: image_paths.append(pos_map_path); logger.info(f"Generated positioning map: {pos_map_path}")
        
    logger.info(f"Total {len(image_paths)} images generated.")

    # --- PDF 생성 ---
    pdf_content = report_text
    if image_paths:
        pdf_content += "\n\n---\n\n## 생성된 시각화 자료\n"
        for img_path in image_paths:
            pdf_content += f"![{os.path.basename(img_path)}]({img_path})\n"

    from app.agents.tools import generate_report_pdf_v2_tool
    pdf_filename = f"{base_filename}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = generate_report_pdf_v2_tool.invoke({"content": pdf_content, "filename": pdf_filename})

    logger.info(f"Visualization & PDF Generation Complete. PDF saved at: {pdf_path}")

    return {
        "final_answer": report_text, # 분석 노드의 텍스트 리포트를 최종 답변으로 설정
        "pdf_path": str(pdf_path),
        "image_paths": [str(p) for p in image_paths]
    }

# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("visualization_gen", visualization_gen_node)
workflow.set_entry_point("visualization_gen")
workflow.add_edge("visualization_gen", END)
visualization_graph = workflow.compile()

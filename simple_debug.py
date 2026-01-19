#!/usr/bin/env python
import pandas as pd
import os
import glob

def debug_csv_search(keyword="디저트", platform="youtube"):
    downloads_dir = "downloads"

    print(f"Searching for CSV files with keyword: {keyword}, platform: {platform}")

    if not os.path.exists(downloads_dir):
        print(f"Downloads directory not found: {downloads_dir}")
        return

    # 모든 CSV 파일 찾기
    all_csv_files = glob.glob(f"{downloads_dir}/*.csv")
    print(f"All CSV files found: {all_csv_files}")

    # 키워드가 파일명에 포함된 파일들 필터링
    csv_files = [f for f in all_csv_files if keyword in os.path.basename(f)]
    print(f"Filtered CSV files containing '{keyword}': {csv_files}")

    if not csv_files:
        print(f"No CSV files found containing keyword '{keyword}'")
        return

    # 가장 최신 파일 선택
    csv_file = max(csv_files, key=os.path.getctime)
    print(f"Selected CSV file: {csv_file}")

    # 파일 읽기 시도
    try:
        encodings = ['utf-8', 'cp949', 'euc-kr']
        df = None

        for encoding in encodings:
            try:
                df = pd.read_csv(csv_file, encoding=encoding)
                print(f"Successfully read CSV with encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error with {encoding}: {e}")
                continue

        if df is None:
            print("Failed to read CSV with any encoding")
            return

        print(f"CSV shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")

        # viewCount 컬럼 확인
        if 'viewCount' in df.columns:
            print("Found viewCount column")
            df['view_count'] = pd.to_numeric(df['viewCount'], errors='coerce')
            df_clean = df.dropna(subset=['view_count', 'title'])
            df_sorted = df_clean.sort_values('view_count', ascending=False)

            top_3 = df_sorted.head(3)
            print("Top 3 videos by view count:")
            for i, (_, row) in enumerate(top_3.iterrows(), 1):
                print(f"{i}. Title: {row.get('title', 'N/A')[:50]}...")
                print(f"   Views: {int(row.get('view_count', 0))}")
                print(f"   Video ID: {row.get('video_id', 'N/A')}")
                print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_csv_search()
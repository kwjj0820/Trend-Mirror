#!/bin/bash

# 1. 가상환경 활성화 (필요시 경로 수정)
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 2. 필요한 디렉토리 생성
mkdir -p logs
mkdir -p downloads
mkdir -p reports
mkdir -p chroma_tm

# 3. 서버 실행
echo "🚀 Starting TrendMirror API Server..."
python main.py
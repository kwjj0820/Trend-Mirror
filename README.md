# Trend-Mirror

TrendMirror는 최신 트렌드를 분석하고, 관련 정보를 수집하여 비즈니스/마케팅 전략 보고서를 생성하는 AI 에이전트 프로젝트입니다. 사용자의 요청을 분석하여 의도를 파악하고, YouTube와 같은 소셜 채널의 데이터를 수집/분석하여 RAG(Retrieval-Augmented Generation)를 통해 신뢰도 높은 리포트를 생성합니다.

## 🚀 주요 기능

-   **의도 분석 및 슬롯 추출**: 사용자의 자연어 요청을 분석하여 '트렌드 분석'과 같은 의도(`intent`)와 분석에 필요한 핵심 정보(`slots` - 주제, 기간 등)를 추출합니다.
-   **YouTube 트렌드 데이터 수집**: `search_query`를 기반으로 YouTube에서 최신 트렌드와 관련된 동영상을 수집하고 분석합니다.
-   **키워드 추출 및 빈도 분석**: 수집된 데이터(제목, 설명)에서 LLM을을 활용하여 핵심 트렌드 키워드를 추출하고, 빈도수를 계산하여 저장합니다.
-   **RAG 기반 리포트 생성**: ChromaDB에 저장된 벡터 데이터를 기반으로, 사용자의 질문과 관련된 정보를 검색하고 Upstage Solar LLM을 활용하여 종합적인 분석 리포트를 생성합니다.
-   **PDF 보고서 자동 생성**: 생성된 텍스트 리포트를 바탕으로 PDF 파일을 자동으로 생성하여 제공합니다.
-   **FastAPI 기반 API 제공**: 에이전트의 모든 기능은 RESTful API 엔드포인트 (`/api/v1/chat`)를 통해 외부에서 쉽게 사용할 수 있습니다.

<<<<<<< HEAD
## 🤖 워크플로우 (Workflow)

TrendMirror는 LangGraph를 기반으로 한 자율 에이전트 워크플로우를 통해 사용자의 요청을 처리합니다. 전체 과정은 여러 서브그래프(에이전트)들의 협력으로 이루어지며, 각 단계의 결과에 따라 동적으로 다음 경로가 결정됩니다.

```mermaid
graph TD;
    Start[사용자 입력] --> StrategyBuild[1. Strategy Build];
    StrategyBuild --> Router[2. Router];
    
    Router --> Chitchat[단순 대화];
    Router --> CacheHit[DB 조회];
    Router --> CacheMiss[신규 분석];

    Chitchat --> End[종료];
    CacheHit --> StrategyGen[4. Strategy Gen];
    
    CacheMiss --> YoutubeProcess[3-A. YouTube Process];
    YoutubeProcess --> KeywordExtract[3-B. Keyword Extract];
    KeywordExtract --> SyncToDB[3-C. Sync to DB];
    SyncToDB --> StrategyGen;

    StrategyGen --> End;
```

---

### **1. 전략 수립 (`strategy_build`)**

-   **상세 동작**: 사용자의 첫 입력을 LLM(Solar)에 전달하여 요청의 의도를 파악합니다. '트렌드 분석' 요청인지, 아니면 '단순 대화(chitchat)'인지 구분하고, 분석에 필요한 핵심 정보(지역, 기간, 목표 등)를 `slots`으로 추출합니다. 또한, 캐싱 및 DB 조회를 위한 `cache_key`를 생성합니다.
-   **파일 출력**: 없음. 모든 결과는 내부 상태(`TMState`)에 저장됩니다.

### **2. 분기 처리 (`router`)**

-   **상세 동작**: `strategy_build` 단계에서 결정된 `intent` 값과 캐시/DB 조회 결과에 따라 워크플로우의 다음 경로를 결정합니다.
    -   **단순 대화일 경우**: 즉시 종료하고 미리 정의된 답변을 반환합니다.
    -   **DB에 관련 정보가 있는 경우 (`CacheHit`)**: 데이터 수집 단계를 건너뛰고, DB에서 조회한 정보를 바탕으로 바로 리포트 생성 단계로 이동합니다.
    -   **새로운 분석이 필요한 경우 (`CacheMiss`)**: `youtube_process` 서브그래프로 이동하여 데이터 수집 및 분석을 시작합니다.

### **3. 데이터 처리 및 동기화**

새로운 트렌드 분석 요청 시, 여러 에이전트가 순차적으로 동작하여 데이터를 수집, 분석하고 DB에 저장합니다.

#### **3-A. 유튜브 데이터 처리 (`youtube_process`)**
-   **상세 동작**:
    1.  사용자 요청(`slots`)을 기반으로 `youtube_crawling_tool`을 호출하여 관련 유튜브 영상 정보를 크롤링합니다.
    2.  크롤링 결과를 `downloads/` 폴더에 CSV 파일로 저장합니다.
    3.  다음 단계인 `keyword_extract`를 호출하며 CSV 파일 경로를 전달합니다.
-   **파일 출력**: `downloads/youtube_{query}_{days}d_real_data.csv`

#### **3-B. 트렌드 키워드 추출 (`keyword_extract`)**
-   **상세 동작**:
    1.  앞서 생성된 크롤링 결과 CSV 파일을 읽어옵니다.
    2.  영상 제목과 설명을 '유튜브 바이럴 트렌드 분석가' 역할을 하는 LLM(solar-pro)에 전달하여, 마케팅에 적합한 구체적인 트렌드 키워드(신조어, 고유명사 등)를 추출합니다.
    3.  추출된 키워드를 원본 데이터에 `trend_keywords`라는 새 컬럼으로 추가하여 새로운 CSV 파일을 생성합니다.
-   **파일 출력**: `downloads/..._with_keywords.csv`

#### **3-C. 벡터 DB 동기화 (`SyncService` 호출)**
-   **상세 동작**: `keyword_extract` 서브그래프의 마지막 단계에서 `SyncService`를 호출합니다.
    1.  키워드가 추가된 CSV 파일의 내용을 분석합니다.
    2.  파일 이름(`음식_youtube_...`)을 파싱하여 `category`와 `sns` 메타데이터를 추출합니다.
    3.  해당 `category`와 `sns`에 해당하는 기존 데이터를 벡터 DB에서 **삭제**합니다.
    4.  영상 제목, 설명, 추출된 키워드 등 모든 정보를 포함하여 새로운 문서를 생성하고 벡터 DB에 **추가**합니다. 이를 통해 DB는 항상 최신 트렌드 정보를 유지합니다.
-   **파일 출력**: 없음. (DB 상태 변경)

### **4. 최종 리포트 생성 (`strategy_gen`)**

-   **상세 동작**:
    1.  `CacheMiss` 경로를 거친 경우, `keyword_extract`의 최종 결과물을 컨텍스트로 사용합니다. `CacheHit`의 경우, DB에서 조회한 데이터를 사용합니다.
    2.  LLM(Solar)에 이 컨텍스트와 함께 최종 리포트 생성을 요청합니다. 리포트는 요약, 핵심 트렌드, 전략 제안, 결론 등을 포함한 마크다운 형식으로 작성됩니다.
    3.  생성된 마크다운 내용을 `generate_report_pdf` 도구에 전달하여 최종 PDF 파일로 변환합니다.
-   **파일 출력**:
    -   `reports/` 디렉토리에 최종 분석 결과가 담긴 **PDF 파일**이 `report_{요청 주제}.pdf` 형식으로 저장됩니다.

### **5. 종료 (`END`)**

-   **상세 동작**: 생성된 리포트(마크다운 텍스트)와 PDF 파일의 경로를 최종 결과로 반환하고 워크플로우를 마칩니다.

## ⚙️ 시작하기 (Getting Started)

이 섹션에서는 프로젝트를 로컬 환경에서 설정하고 실행하는 방법을 안내합니다.

### 1. 사전 요구사항

- Python 3.12 이상
- [uv](https://github.com/astral-sh/uv): 빠른 Python 패키지 설치 및 관리를 위한 도구

### 2. 환경 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 필요한 API 키를 입력합니다.

```.env
UPSTAGE_API_KEY="YOUR_UPSTAGE_API_KEY"
YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY"
```

### 3. 가상 환경 생성 및 종속성 설치

`uv`를 사용하여 가상 환경을 만들고 `pyproject.toml`에 명시된 종속성을 설치합니다.

```bash
# 1. 가상 환경 생성 (.venv 폴더 생성)
uv venv

# 2. 종속성 설치 (uv.lock 또는 pyproject.toml 기반)
uv sync
```

### 4. 가상 환경 활성화

개발을 시작하거나 서버를 실행하기 전에, 생성된 가상 환경을 활성화해야 합니다. 사용 중인 쉘에 맞는 명령어를 실행하세요.

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**macOS / Linux (Bash, Zsh):**
```sh
source .venv/bin/activate
```
활성화되면 터미널 프롬프트 앞에 `(.venv)`가 표시됩니다.

### 5. 서버 실행

가상 환경이 활성화된 상태에서 다음 명령어를 실행하여 FastAPI 서버를 시작합니다.

```bash
uvicorn app.main:app --reloaduv 
```

- `--reload` 옵션은 코드 변경 시 서버를 자동으로 재시작하여 개발에 유용합니다.
- 서버가 정상적으로 실행되면, 브라우저에서 `http://localhost:8000/docs` 로 접속하여 API 문서를 확인할 수 있습니다.
=======
## ⛓️ 핵심 워크플로우

TrendMirror는 LangGraph를 기반으로 여러 에이전트(서브그래프)가 유기적으로 협력하여 사용자의 요청을 처리합니다. 전체 워크플로우는 다음과 같습니다.

```mermaid
graph TD
    A(사용자 요청) --> B[Strategy Build];
    B -- "의도/주제 추출" --> C{Router};
    C -- "트렌드 분석 요청" --> D[YouTube Process];
    C -- "일반 대화" --> G[간단한 응답 후 종료];
    
    subgraph "데이터 수집 및 처리"
        D -- "1. 유튜브 크롤링" --> E[Keyword Extraction];
        E -- "2. 키워드 추출" --> F[Vector DB 저장];
    end
    
    F --> H[Strategy Gen];

    subgraph "리포트 생성 (RAG)"
        H -- "3. 관련 정보 검색" --> F;
        H -- "4. LLM 리포트 생성" --> I(PDF 생성);
    end

    I --> J(API 최종 응답);
```

1.  **`[Strategy Build]` - 의도 분석 및 계획 수립**
    *   사용자의 초기 입력을 받아 LLM을 통해 `intent`(의도)와 `slots`(핵심 정보)를 추출합니다.
    *   **의도**: `trendmirror`(트렌드 분석) 또는 `chitchat`(단순 대화)으로 분류합니다.
    *   **슬롯**: `domain`(구체적 주제)과 `search_query`(DB 검색 및 크롤링에 사용될 핵심 카테고리) 등을 추출합니다.

2.  **`[Router]` - 작업 분기**
    *   `strategy_build`에서 파악된 의도에 따라 다음 작업을 결정합니다.
    *   `chitchat`일 경우: 간단한 응답 후 워크플로우를 종료합니다.
    *   `trendmirror`일 경우: 데이터 처리 단계로 이동합니다.

3.  **`[YouTube Process]` - 데이터 수집**
    *   `slots`에 담긴 `search_query`를 사용하여 `youtube_crawling_tool`을 호출합니다.
    *   최신 트렌드를 반영하기 위해, 지정된 기간(`days`)과 페이지 수(`pages`)만큼 YouTube 동영상을 검색하여 원본 데이터(CSV)를 저장합니다.

4.  **`[Keyword Extraction]` - 키워드 추출 및 저장**
    *   수집된 YouTube 데이터(제목, 설명)를 LLM에 전달하여 핵심 트렌드 키워드를 추출합니다.
    *   추출된 키워드의 빈도수를 계산하고, `(SNS, 카테고리, 날짜)`를 기준으로 Vector DB(ChromaDB)에 임베딩과 함께 저장합니다. 이 데이터는 나중에 RAG의 기반이 됩니다.

5.  **`[Strategy Gen]` - RAG 기반 리포트 생성**
    *   사용자의 최종 질문과 `search_query`(`category`)를 바탕으로 DB에서 가장 관련성 높은 키워드와 문서들을 검색(Retrieve)합니다.
    *   검색된 데이터를 풍부한 컨텍스트로 재구성하여 Solar LLM에 전달하고, 종합적인 트렌드 분석 리포트 생성을 요청(Generate)합니다.
    *   생성된 텍스트 리포트는 PDF 파일로 변환되어 `reports/` 디렉토리에 저장됩니다.

6.  **`[Final Response]` - 최종 응답**
    *   생성된 리포트 내용과 PDF 파일 경로를 API 응답으로 사용자에게 반환합니다.

## ⚙️ 기술 스택

-   **Backend**: FastAPI, Uvicorn
-   **AI/LLM**: LangGraph, LangChain, Upstage Solar, ChromaDB
-   **Package Management**: uv
-   **Others**: Pydantic, python-dotenv
>>>>>>> bbb851990005b22661d992cd7383fad2c387af79

## 📁 프로젝트 구조

```
.
├── .env.example        # 환경 변수 예시 파일
├── .gitignore
├── app/                # 핵심 애플리케이션 로직
│   ├── main.py         # FastAPI 앱 초기화 및 설정
│   ├── agents/         # LangGraph 기반 에이전트 및 워크플로우
│   ├── api/            # API 라우터 및 엔드포인트
│   ├── core/           # DB 연결, LLM 클라이언트, 로거 등 핵심 모듈
│   ├── models/         # Pydantic 스키마
│   ├── repository/     # 데이터베이스 및 외부 API 클라이언트
│   └── service/        # 비즈니스 로직 서비스
├── chroma_tm/          # ChromaDB 데이터 저장소
├── downloads/          # 크롤링 데이터 임시 저장
├── logs/               # 실행 로그
├── reports/            # 생성된 PDF 보고서
├── resources/          # 폰트 등 정적 리소스
├── scripts/            # DB 동기화 등 보조 스크립트
├── main.py             # (현재 사용되지 않음, app/main.py가 메인)
├── pyproject.toml      # 프로젝트 의존성 및 메타데이터
└── README.md
```

## 💿 설치 및 실행 방법

### 1. 프로젝트 복제

```bash
git clone https://github.com/your-username/Trend-Mirror.git
cd Trend-Mirror
```

### 2. 가상 환경 생성 및 활성화

Python 3.12 이상이 필요합니다. `uv` 사용을 권장합니다.

```bash
# uv 설치 (아직 없다면)
pip install uv

# 가상 환경 생성 및 활성화
uv venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
```

### 3. 환경 변수 설정

`.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 파일 내에 자신의 API 키를 입력합니다.

```bash
cp .env.example .env
```

```.env
# .env
UPSTAGE_API_KEY="YOUR_UPSTAGE_API_KEY"
YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY"
NAVER_CLIENT_ID="YOUR_NAVER_CLIENT_ID"
NAVER_CLIENT_SECRET="YOUR_NAVER_CLIENT_SECRET"
```

### 4. 의존성 설치

`pyproject.toml`에 명시된 라이브러리들을 설치합니다.

```bash
uv sync
```

### 5. 서버 실행

Uvicorn을 사용하여 FastAPI 서버를 실행합니다.

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 `http://localhost:8000/docs`에서 API 문서를 확인할 수 있습니다.

## 📖 사용 방법

### 1. API를 통한 트렌드 분석 요청

`POST /api/v1/chat` 엔드포인트로 분석하고 싶은 주제를 담아 요청을 보냅니다.

**Curl 예시 (Windows cmd 기준):**

```shell
curl -X POST "http://localhost:8000/api/v1/chat" -H "Content-Type: application/json" -d "{\"query\": \"요즘 유행하는 디저트\", \"thread_id\": \"my_trend_analysis_1\"}"
```
### 2. 스크립트를 이용한 수동 DB 동기화

수집된 키워드 빈도수 CSV 파일이 있는 경우, 아래 스크립트를 사용하여 수동으로 Vector DB에 동기화할 수 있습니다.

```bash
python scripts/sync_trend_db.py [CSV_파일_경로]

# 예시
python scripts/sync_trend_db.py downloads/youtube_디저트_20260114_30d_real_data_keyword_frequencies.csv
```
# Trend-Mirror

TrendMirror는 Upstage AI Lab 부트캠프를 위해 제작된 AI 에이전트 프로젝트입니다. 최신 트렌드를 분석하고, 관련 정보를 수집하여 비즈니스/마케팅 전략 보고서를 생성하는 것을 목표로 합니다.

## 🚀 주요 기능

-   **트렌드 분석 및 리포트 생성**: 사용자가 궁금해하는 주제(예: "요즘 유행하는 음식")를 입력하면 관련 최신 PDF 문서를 검색, 다운로드 및 분석하여 Markdown 형식의 리포트와 PDF 파일을 생성합니다.
-   **의도 파악 및 분류**: 사용자의 입력이 트렌드 분석과 관련된 요청인지, 단순한 잡담인지 파악하여 그에 맞는 답변을 제공합니다.
-   **RAG (Retrieval-Augmented Generation)**: Upstage의 Solar LLM과 ChromaDB를 활용하여, 검색된 정보를 바탕으로 신뢰도 높은 답변을 생성합니다.
-   **자동화된 워크플로우**: LangGraph를 기반으로 에이전트들이 유기적으로 협력하여 '의도 파악 → 정보 검색/추출 → 리포트 생성'의 과정을 자동 수행합니다.

## 📁 디렉토리 구조

```
.
├── .gitignore
├── main.py
├── pyproject.toml
├── README.md
├── app
│   ├── deps.py
│   ├── main.py
│   ├── agents
│   │   ├── state.py
│   │   ├── tools.py
│   │   ├── utils.py
│   │   ├── workflow.py
│   │   └── subgraphs
│   │       ├── insight_extract.py
│   │       ├── strategy_build.py
│   │       └── strategy_gen.py
│   ├── api
│   │   └── routes
│   │       └── chat.py
│   ├── core
│   │   ├── db.py
│   │   ├── llm.py
│   │   └── logger.py
│   ├── models
│   │   └── schemas
│   │       └── chat.py
│   ├── repository
│   │   ├── client
│   │   │   ├── base.py
│   │   │   ├── llm_client.py
│   │   │   └── search_client.py
│   │   └── vector
│   │       └── vector_repo.py
│   └── service
│       ├── agent_service.py
│       ├── embedding_service.py
│       └── vector_service.py
├── chroma_tm/
├── downloads/
├── logs/
└── reports/
```

## 📄 파일 설명

### 최상위 디렉토리

-   `main.py`: FastAPI 애플리케이션을 실행하는 엔트리포인트입니다. `uvicorn`을 사용하여 서버를 시작합니다.
-   `pyproject.toml`: 프로젝트의 의존성 및 메타데이터를 관리합니다.
-   `.gitignore`: Git 버전 관리에서 제외할 파일 및 디렉토리 목록을 정의합니다.
-   `README.md`: 프로젝트에 대한 설명 문서입니다.

### `app/`

-   `main.py`: FastAPI 앱 인스턴스를 생성하고, CORS 미들웨어, 라우터 등을 설정하는 메인 애플리케이션 파일입니다.
-   `deps.py`: FastAPI의 의존성 주입(Dependency Injection) 시스템을 설정합니다. 각 서비스와 리포지토리의 인스턴스를 생성하고 관리합니다.

#### `app/agents/`

-   `workflow.py`: LangGraph를 사용하여 전체 에이전트 워크플로우(그래프)를 정의하고 컴파일합니다.
-   `state.py`: 워크플로우의 각 단계 간에 데이터를 전달하는 데 사용되는 공유 상태(`TMState`)를 정의합니다.
-   `tools.py`: 에이전트가 사용하는 도구(PDF 다운로드, 문서 파싱, 리포트 생성 등)를 정의합니다. `@tool` 데코레이터를 사용하여 LangChain 도구로 만듭니다.
-   `utils.py`: JSON 파싱, 토큰 수 계산 등 워크플로우 전반에서 사용되는 유틸리티 함수들을 포함합니다.
-   **`app/agents/subgraphs/`**: 각 에이전트의 구체적인 로직을 포함하는 서브그래프들입니다.
    -   `strategy_build.py`: 사용자의 입력을 분석하여 의도(`intent`)와 주요 정보(`slots`)를 추출합니다.
    -   `insight_extract.py`: `strategy_build`에서 추출된 정보를 바탕으로 웹에서 관련 문서를 검색, 다운로드하고 RAG를 위한 데이터베이스를 구축합니다.
    -   `strategy_gen.py`: `insight_extract`에서 처리된 데이터를 바탕으로 최종 트렌드 리포트를 생성하고 PDF로 저장합니다.

#### `app/api/`

-   `routes/chat.py`: `/api/v1/chat` 엔드포인트를 정의합니다. 사용자의 요청을 받아 `AgentService`를 호출하고 결과를 반환합니다.

#### `app/core/`

-   `llm.py`: Upstage LLM(채팅, 임베딩 모델)을 가져오는 함수를 제공합니다.
-   `db.py`: ChromaDB와의 연결을 관리하는 싱글톤 클래스(`ChromaDBConnection`)를 정의합니다.
-   `logger.py`: 프로젝트 전반에서 사용될 로거를 설정합니다. 로그는 콘솔과 날짜별 로그 파일(`logs/`)에 모두 기록됩니다.

#### `app/models/`

-   `schemas/chat.py`: API 요청(`ChatRequest`) 및 응답(`ChatResponse`)의 데이터 구조를 Pydantic 모델로 정의합니다.

#### `app/repository/`

-   `client/base.py`: LLM 및 검색 클라이언트에 대한 추상 기반 클래스(ABC)를 정의합니다.
-   `client/llm_client.py`: Upstage API를 사용하여 채팅 및 임베딩 모델을 가져오는 `UpstageClient`를 구현합니다.
-   `client/search_client.py`: Serper.dev API를 사용하여 웹 검색을 수행하는 `SerperSearchClient`를 구현합니다.
-   `vector/vector_repo.py`: 벡터 데이터베이스(ChromaDB)에 대한 데이터 추가(Upsert) 및 검색(Query) 작업을 수행하는 `ChromaDBRepository`를 구현합니다.

#### `app/service/`

-   `agent_service.py`: 에이전트 워크플로우를 실행하고 그 결과를 반환하는 비즈니스 로직을 담당합니다.
-   `embedding_service.py`: 텍스트를 벡터로 변환하는 임베딩 생성 로직을 담당합니다.
-   `vector_service.py`: `ChromaDBRepository`와 `EmbeddingService`를 사용하여 문서 저장 및 검색과 관련된 비즈니스 로직을 처리합니다.

### 기타 디렉토리

-   `chroma_tm/`: ChromaDB 데이터가 영구 저장되는 디렉토리입니다.
-   `downloads/`: 웹에서 다운로드한 PDF 파일이 임시 저장되는 디렉토리입니다.
-   `logs/`: 날짜별로 에이전트 실행 로그가 저장되는 디렉토리입니다.
-   `reports/`: 생성된 최종 PDF 리포트가 저장되는 디렉토리입니다.

## ⚙️ 실행 방법

### 1. 환경 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 필요한 API 키를 입력합니다.

```
UPSTAGE_API_KEY="YOUR_UPSTAGE_API_KEY"
SERPER_API_KEY="YOUR_SERPER_API_KEY"
```

### 2. 의존성 설치

`pyproject.toml` 파일이 있는 루트 디렉토리에서 다음 명령어를 실행하여 필요한 라이브러리를 설치합니다. `uv` 와 같은 가상환경 및 패키지 관리 도구 사용을 권장합니다.

```bash
uv sync
```

### 3. 서버 실행

가상환경이 활성화된 상태에서, 다음 명령어를 실행하여 FastAPI 서버를 시작합니다.
필요한 디렉토리(logs, downloads 등)는 서버 시작 시 자동으로 생성됩니다.

```bash
python main.py
```

서버가 정상적으로 실행되면, `http://localhost:8000/docs` 에서 API 문서를 확인할 수 있습니다.
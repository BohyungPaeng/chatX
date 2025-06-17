# 🔧 ChatX FastAPI 백엔드

> OpenAI API를 활용한 멀티모달 AI 백엔드 서비스  
> 채팅, 웹검색, 이미지분석, 파일질의 기능 제공

## ✨ API 기능

### 💬 **채팅 API**
- GPT-4.1 기반 텍스트 대화
- 실시간 스트리밍 응답
- 대화 컨텍스트 관리

### 🔍 **웹 검색 API**  
- 실시간 웹 정보 검색
- 검색 결과 인용 정보 제공
- GPT-4o-search-preview 모델 활용

### 🖼️ **이미지 분석 API**
- 이미지 업로드 및 AI 분석
- GPT-4 Vision 모델 활용
- 스트리밍 응답 지원

### 📁 **파일 질의 API**
- PDF, DOCX, PPTX 파일 업로드
- OpenAI Vector Store 활용
- 파일 내용 기반 질의응답

## 🚀 설치 및 실행

### 📋 사전 요구사항
- Python 3.8+
- OpenAI API Key

### ⚡ 빠른 시작

1. **의존성 설치**:
   ```bash
   pip install -r requirements.txt
   ```

2. **환경 변수 설정**:
   `.env` 파일을 생성하고 다음 변수를 설정:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   HOST=0.0.0.0
   PORT=8000
   GPT_MODEL=gpt-4-1106-preview
   ```

3. **서버 실행**:
   ```bash
   python run.py
   ```

4. **접속 확인**:
   - API 서버: http://localhost:8000
   - API 문서: http://localhost:8000/docs
   - ReDoc 문서: http://localhost:8000/redoc

## 📖 API 엔드포인트

### 💬 채팅 API

#### `POST /api/chat`
채팅 메시지를 처리하고 GPT 응답을 반환합니다.

**요청 예시:**
```json
{
  "messages": [
    {
      "role": "user", 
      "content": "안녕하세요, GPT-4.1!"
    }
  ],
  "model": "gpt-4.1",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**응답 예시:**
```json
{
  "response": "안녕하세요! 무엇을 도와드릴까요?",
  "model": "gpt-4.1",
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 20,
    "total_tokens": 35
  },
  "citations": []
}
```

#### `POST /api/chat/stream`
실시간 스트리밍 채팅 응답을 제공합니다.

**응답 형식:** Server-Sent Events (SSE)
```
data: {"content": "안녕", "is_streaming": true, "model": "gpt-4.1"}
data: {"content": "하세요!", "is_streaming": true, "model": "gpt-4.1"}
data: {"content": "", "is_streaming": false, "model": "gpt-4.1"}
data: [DONE]
```

### 🔍 웹 검색 API

#### `POST /api/web-search`
웹 검색을 수행하고 결과를 반환합니다.

**요청 예시:**
```json
{
  "query": "2024년 AI 동향",
  "model": "gpt-4o-search-preview",
  "max_tokens": 1000
}
```

**응답 예시:**
```json
{
  "response": "2024년 AI 동향은...",
  "model": "gpt-4o-search-preview",
  "usage": {...},
  "citations": [
    {
      "url": "https://example.com/article",
      "title": "AI 동향 분석",
      "start_index": 15,
      "end_index": 45
    }
  ]
}
```

### 🖼️ 이미지 분석 API

#### `POST /api/analyze-image`
이미지를 분석하고 설명을 생성합니다.

**요청 예시:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "prompt": "이 이미지에 무엇이 있나요?",
  "model": "gpt-4.1",
  "max_tokens": 500,
  "conversation_history": []
}
```

#### `POST /api/analyze-image/stream`
이미지 분석 결과를 스트리밍으로 제공합니다.

### 📁 파일 업로드 및 질의 API

#### `POST /api/upload-file`
파일을 OpenAI에 업로드하고 벡터 스토어를 생성합니다.

**요청:** `multipart/form-data`
```bash
curl -X POST "http://localhost:8000/api/upload-file" \
  -F "file=@document.pdf"
```

**응답 예시:**
```json
{
  "success": true,
  "file_id": "file-abc123",
  "vector_store_id": "vs-xyz789"
}
```

#### `POST /api/query-file`
업로드된 파일에 대해 질의를 수행합니다.

**요청 예시:**
```json
{
  "query": "이 문서의 주요 내용은 무엇인가요?",
  "vector_store_id": "vs-xyz789",
  "model": "gpt-4o",
  "conversation_history": []
}
```

**응답 예시:**
```json
{
  "response": "이 문서의 주요 내용은...",
  "annotations": [
    {
      "type": "file_citation",
      "index": 10,
      "file_id": "file-abc123",
      "filename": "document.pdf",
      "quote": "문서에서 인용된 텍스트...",
      "score": 0.95
    }
  ],
  "search_results": [...]
}
```

### 📋 기타 API

#### `GET /api/models`
사용 가능한 AI 모델 목록을 반환합니다.

#### `GET /api/health`
서버 상태를 확인합니다.

## 🔧 개발 정보

### 📁 프로젝트 구조

```
api/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI 앱 설정
│   ├── config.py         # 환경 설정
│   ├── models.py         # Pydantic 모델
│   ├── routers.py        # API 라우터
│   └── services.py       # OpenAI 서비스 로직
├── temp/                 # 임시 파일 저장
├── requirements.txt      # Python 의존성
├── run.py               # 서버 실행 스크립트
├── env_example          # 환경변수 예시
└── README.md            # 이 파일
```

### 🔑 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 (필수) | - |
| `HOST` | 서버 호스트 | `0.0.0.0` |
| `PORT` | 서버 포트 | `8000` |
| `GPT_MODEL` | 기본 GPT 모델 | `gpt-4-1106-preview` |

### 🧪 테스트

개발용 테스트 스크립트들:
```bash
python api_test.py          # 기본 API 테스트
python responses_test.py    # Response API 테스트  
python network_test.py      # 네트워크 연결 테스트
python file_query_test.py   # 파일 질의 테스트
```

### 🔒 보안 설정

**SSL 인증서 문제 해결** (회사망 환경):
```python
# services.py에서 적용됨
http_client = httpx.Client(verify=False)
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=http_client
)
```

**CORS 설정**:
```python
# main.py에서 프론트엔드 연동을 위한 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🚨 문제 해결

### SSL 인증서 오류
```
CERTIFICATE_VERIFY_FAILED
```
**해결방법**: `services.py`에서 `verify=False` 설정 적용됨

### 모델 호환성 오류
```
Model not found
```
**해결방법**: `services.py`의 모델 매핑 확인

### 파일 업로드 오류
```
Missing vector_store_ids
```
**해결방법**: Response API 사용하여 해결됨

## 📚 관련 문서

- [OpenAI API 문서](https://platform.openai.com/docs/api-reference)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [ChatX 메인 문서](../README.md)

---

**API 서버 v1.0 - Assurance-Digital**

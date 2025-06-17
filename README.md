# 🚀 ChatX - AI 채팅 플랫폼

> **Next.js + FastAPI**로 구축된 AI 파워드 채팅 플랫폼  
> OpenAI API를 활용한 텍스트 대화, 웹 검색, 이미지 분석, 파일 질의 기능

## ✨ 주요 기능

### 💬 **멀티모달 AI 채팅**
- **텍스트 대화**: GPT-4.1 기반 자연어 대화
- **웹 검색**: 실시간 웹 정보 검색 및 인용
- **이미지 분석**: 이미지 업로드 및 AI 분석
- **파일 질의**: PDF, DOCX, PPTX 파일 업로드 후 내용 질의

### 🎨 **Modern UI/UX**
- **반응형 디자인**: 모바일/데스크톱 최적화
- **다크/라이트 테마**: 사용자 환경 설정
- **실시간 스트리밍**: 답변 실시간 표시
- **파일 드래그&드롭**: 직관적인 파일 업로드

### 🔧 **기술 스택**
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, Python, OpenAI API
- **Features**: Real-time streaming, Vector search, File processing

## 🚀 빠른 시작

### 📋 사전 요구사항
- **Node.js** 18+ 
- **Python** 3.8+
- **OpenAI API Key** ([발급받기](https://platform.openai.com/api-keys))

### ⚡ 설치 및 실행

```bash
# 1. 프로젝트 클론
git clone https://github.com/Assurance-Digital/ChatX.git
cd ChatX

# 2. 의존성 설치
npm install                              # 프론트엔드
pip install -r api/requirements.txt      # 백엔드

# 3. 환경변수 설정
# api/.env 파일 생성
echo "OPENAI_API_KEY=your_api_key_here" > api/.env

# 4. 서버 실행
npm run dev                              # 프론트엔드 (3000포트)
python api/run.py                        # 백엔드 (8000포트)
```

### 🌐 접속
- **프론트엔드**: http://localhost:3000
- **API 문서**: http://localhost:8000/docs

## 📁 프로젝트 구조

```
ChatX/
├── app/                    # Next.js 앱 라우터
├── components/             # React 컴포넌트
│   ├── ui/                # shadcn/ui 컴포넌트
│   ├── chat-area.tsx      # 메인 채팅 영역
│   ├── file-upload.tsx    # 파일 업로드 컴포넌트
│   └── ...
├── api/                   # FastAPI 백엔드
│   ├── app/              # API 애플리케이션
│   │   ├── main.py       # FastAPI 앱
│   │   ├── routers.py    # API 라우터
│   │   ├── services.py   # OpenAI 서비스
│   │   └── models.py     # 데이터 모델
│   ├── requirements.txt  # Python 의존성
│   └── run.py           # 서버 실행
├── lib/                  # 유틸리티
├── hooks/                # React 훅
└── public/              # 정적 파일
```

## 🔑 환경변수 설정

### `api/.env` 파일 생성
```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# 서버 설정
HOST=0.0.0.0
PORT=8000

# 모델 설정
GPT_MODEL=gpt-4-1106-preview
```

## 📖 API 사용법

### 💬 채팅 API
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "안녕하세요!"}],
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

### 🔍 웹 검색 API
```bash
curl -X POST "http://localhost:8000/api/web-search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2024년 AI 동향",
    "max_tokens": 1000
  }'
```

### 📁 파일 업로드 API
```bash
curl -X POST "http://localhost:8000/api/upload-file" \
  -F "file=@document.pdf"
```

## 🔧 개발 가이드

### 프론트엔드 개발
```bash
npm run dev          # 개발 서버
npm run build        # 프로덕션 빌드
npm run lint         # ESLint 검사
```

### 백엔드 개발
```bash
cd api
python run.py        # 개발 서버 (auto-reload)
python -m pytest    # 테스트 실행
```

## 🌟 주요 특징

### 🔒 **보안**
- API 키 환경변수 관리
- CORS 설정
- SSL 인증서 호환성 (회사망 환경)

### ⚡ **성능**
- 실시간 스트리밍 응답
- 벡터 검색 최적화
- 파일 임시 저장 관리

### 🎯 **사용성**
- 직관적인 UI/UX
- 드래그&드롭 파일 업로드
- 다양한 파일 형식 지원

## 🚨 문제 해결

### SSL 인증서 오류
```python
# api/app/services.py에서 이미 해결됨
http_client = httpx.Client(verify=False)
```

### 모델 호환성
```python
# 모델 매핑 설정으로 해결
model_mapping = {
    "gpt-4o": "gpt-4-1106-preview",
    # ...
}
```

## 📞 지원

- **이슈 신고**: [GitHub Issues](https://github.com/Assurance-Digital/ChatX/issues)
- **API 문서**: http://localhost:8000/docs
- **OpenAI 문서**: https://platform.openai.com/docs

---

**Developed with ❤️ by Assurance-Digital Team** 
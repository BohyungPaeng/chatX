# api/test_embedding.py (새 파일 생성)
import os
from sentence_transformers import SentenceTransformer

def test_cached_model():
    """캐시된 임베딩 모델 테스트"""
    try:
        print("🔍 캐시된 모델 확인 중...")
        
        # 오프라인 모드로 모델 로드 시도
        # model = SentenceTransformer('intfloat/multilingual-e5-base', cache_folder=r"C:\Users\bpaeng001\.cache\huggingface")
        
        # 💡 캐시 경로를 정확히 지정하지 말고, 기본 캐시 활용
        model = SentenceTransformer('intfloat/multilingual-e5-base', local_files_only=True, token=False)
        
        # 간단한 테스트
        test_texts = ["안녕하세요", "Hello world"]
        embeddings = model.encode(test_texts)
        
        print(f"✅ 모델 로드 성공!")
        print(f"📐 임베딩 차원: {embeddings.shape}")
        print(f"🧪 테스트 완료: {len(test_texts)}개 텍스트 임베딩")
        
        return True
        
    except Exception as e:
        print(f"❌ 모델 로드 실패: {e}")
        return False

if __name__ == "__main__":
    test_cached_model()
    # import os
    # # from transformers import AutoModel

    # # 실제 캐시 위치 찾기
    # cache_dir = os.environ.get('HF_HOME', 
    #         os.environ.get('HUGGINGFACE_HUB_CACHE', 
    #         os.path.expanduser('~/.cache/huggingface')))
    # print(f"실제 캐시: {cache_dir}")

    # # 또는 transformers 라이브러리의 기본 캐시 확인
    # from transformers import TRANSFORMERS_CACHE
    # print(f"Transformers 캐시: {TRANSFORMERS_CACHE}")
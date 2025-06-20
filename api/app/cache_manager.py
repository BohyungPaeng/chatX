import pickle
import gzip
import os
import time
import re
from pathlib import Path
from typing import Dict, Optional, List

class PDFCacheManager:
    """PDF 캐시 전용 관리 클래스"""
    
    def __init__(self, cache_dir: str = "pdf_cache"):
        self.cache_dir = Path(cache_dir)
        print(self.cache_dir, " is loaded")
        self.cache_dir.mkdir(exist_ok=True)
        self.memory_cache = {}  # 메모리 캐시
    
    def save(self, filename: str, cache_data: dict) -> bool:
        """
        캐시 저장 (메모리 + 압축 파일)
        
        Args:
            filename: PDF 파일명
            cache_data: 저장할 캐시 데이터
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 메모리 캐시에 저장
            self.memory_cache[filename] = cache_data
            
            # 압축 파일로 저장
            cache_file = self.cache_dir / f"{filename}.pkl.gz"
            
            save_data = {
                'page_texts': cache_data.get('page_texts', []),
                'total_pages': cache_data.get('total_pages', 0),
                'filename': cache_data.get('filename', filename),
                'processing_method': cache_data.get('processing_method', 'unknown'),
                'saved_at': time.time()
            }
            
            with gzip.open(cache_file, 'wb') as f:
                pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            file_size = os.path.getsize(cache_file) / 1024  # KB
            print(f"💾 캐시 저장 완료: {filename} ({file_size:.1f}KB)")
            return True
            
        except Exception as e:
            print(f"⚠️ 캐시 저장 실패: {filename} - {e}")
            return False
    
    def load(self, filename: str, verbose:bool = False) -> Optional[dict]:
        """
        캐시 로드 (메모리 우선, 없으면 파일에서)
        
        Args:
            filename: PDF 파일명
            
        Returns:
            dict or None: 캐시 데이터
        """
        # 1. 메모리 캐시 확인
        if filename in self.memory_cache:
            if verbose:
                print(f"📝 메모리에서 캐시 로드: {filename}")
            return self.memory_cache[filename]
        
        # 2. 파일 캐시 확인
        cache_file = self.cache_dir / f"{filename}.pkl.gz"
        if cache_file.exists():
            try:
                with gzip.open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                
                # 메모리에 다시 로드
                self.memory_cache[filename] = data
                print(f"📁 파일에서 캐시 로드: {filename}")
                return data
                
            except Exception as e:
                print(f"⚠️ 파일 캐시 로드 실패: {filename} - {e}")
                # 손상된 캐시 파일 삭제
                try:
                    cache_file.unlink()
                    print(f"🗑️ 손상된 캐시 파일 삭제: {filename}")
                except:
                    pass
        
        return None
    
    def exists(self, filename: str) -> bool:
        """캐시 존재 여부 확인"""
        return (filename in self.memory_cache or 
                (self.cache_dir / f"{filename}.pkl.gz").exists())
    
    def delete(self, filename: str) -> bool:
        """캐시 삭제"""
        try:
            # 메모리에서 삭제
            if filename in self.memory_cache:
                del self.memory_cache[filename]
            
            # 파일에서 삭제
            cache_file = self.cache_dir / f"{filename}.pkl.gz"
            if cache_file.exists():
                cache_file.unlink()
            
            print(f"🗑️ 캐시 삭제 완료: {filename}")
            return True
            
        except Exception as e:
            print(f"⚠️ 캐시 삭제 실패: {filename} - {e}")
            return False
    
    def cleanup_old(self, days: int = 7) -> int:
        """
        오래된 캐시 파일 정리
        
        Args:
            days: 보관 기간 (일)
            
        Returns:
            int: 삭제된 파일 수
        """
        current_time = time.time()
        deleted_count = 0
        
        for cache_file in self.cache_dir.glob("*.pkl.gz"):
            try:
                file_age = current_time - cache_file.stat().st_mtime
                if file_age > days * 24 * 3600:
                    # 메모리에서도 제거
                    filename = cache_file.stem.replace('.pkl', '')
                    if filename in self.memory_cache:
                        del self.memory_cache[filename]
                    
                    cache_file.unlink()
                    deleted_count += 1
                    print(f"🗑️ 오래된 캐시 삭제: {cache_file.name}")
                    
            except Exception as e:
                print(f"⚠️ 캐시 정리 중 오류: {cache_file.name} - {e}")
        
        return deleted_count
    
    def get_info(self) -> dict:
        """캐시 상태 정보"""
        cache_files = list(self.cache_dir.glob("*.pkl.gz"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            "memory_cache_count": len(self.memory_cache),
            "file_cache_count": len(cache_files),
            "total_size_mb": total_size / (1024 * 1024),
            "cached_files": list(self.memory_cache.keys()),
            "file_cache_files": [f.stem.replace('.pkl', '') for f in cache_files]
        }
    
    def clear_all(self) -> bool:
        """모든 캐시 삭제"""
        try:
            # 메모리 캐시 삭제
            self.memory_cache.clear()
            
            # 파일 캐시 삭제
            for cache_file in self.cache_dir.glob("*.pkl.gz"):
                cache_file.unlink()
            
            print("🗑️ 모든 캐시 삭제 완료")
            return True
            
        except Exception as e:
            print(f"⚠️ 캐시 전체 삭제 실패: {e}")
            return False

# 전역 캐시 매니저 인스턴스
pdf_cache_manager = PDFCacheManager()

def build_page_content_map(filename: str) -> dict[int, str]:
    """
    SearchIndex 외부에서 사용할 수 있는 페이지 컨텐츠 맵 생성
    SearchIndex.build_page_map 기능을 독립적으로 분리
    """
    page_content_map = {}
    
    try:
        cache_data = pdf_cache_manager.load(filename)
        if not cache_data or 'page_texts' not in cache_data:
            return page_content_map
            
        page_texts = cache_data['page_texts']
        
        for page_text in page_texts:
            # 기존 _extract_page_content 로직 재사용
            match = re.match(r'## 📄 페이지 (\d+)\n\n(.*)', page_text, re.DOTALL)
            if match:
                page_num = int(match.group(1))
                content = match.group(2).strip()
                page_content_map[page_num] = content
        
        print(f"📄 페이지 맵 구축 완료: {len(page_content_map)}개 페이지")
        
    except Exception as e:
        print(f"❌ 페이지 맵 구축 실패: {e}")
    
    return page_content_map



if __name__ == "__main__":
    map = build_page_content_map("Guide to Taiwan's semiconductor industry 3.pdf")
    print(map)
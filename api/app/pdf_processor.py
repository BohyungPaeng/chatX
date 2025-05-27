# api/app/pdf_processor.py
"""
PDF 배치 처리 - 간결하고 아름다운 버전
기존 services 함수들을 재사용하여 중복 제거
"""

import time
import fitz
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import threading
from .services import convert_pdf_page_to_base64, analyze_image
from .models import ImageAnalysisRequest

# PDF 처리 관련 상수
PDF_BATCH_SIZE = 8  # 배치당 처리할 페이지 수
PDF_PROCESSING_TIMEOUT = 180  # 처리 타임아웃 (초)
PDF_MAX_FILE_SIZE = 50 * 1024 * 1024  # 최대 파일 크기 (50MB)
TOP_K_MAX = 10  # 검색 결과 최대 개수
TOP_K_MIN = 1   # 검색 결과 최소 개수

class PDFBatchProcessor:
    """PDF 배치 처리를 담당하는 클래스"""
    
    def __init__(self, pdf_content: bytes, filename: str):
        self.pdf_content = pdf_content
        self.filename = filename
        self.processed_pages = 0
        self.total_pages = 0
        self.lock = threading.Lock()
        self.start_time = None
        self.page_data = {}  # {페이지번호: PDF바이트} 딕셔너리
        
    def get_total_pages(self) -> int:
        """PDF 총 페이지 수 반환"""
        try:
            doc = fitz.open(stream=self.pdf_content, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            return total_pages
        except Exception as e:
            print(f"Error getting total pages: {str(e)}")
            return 0
    
    def create_page_data(self) -> bool:
        """
        각 페이지를 독립된 PDF 바이트로 생성
        page_data = {1: pdf_bytes_1, 2: pdf_bytes_2, ...}
        
        Returns:
            bool: 생성 성공 여부
        """
        try:
            print(f"Creating page data for {self.total_pages} pages...")
            
            source_doc = fitz.open(stream=self.pdf_content, filetype="pdf")
            
            for page_num in range(self.total_pages):
                try:
                    # 단일 페이지 PDF 생성
                    single_page_doc = fitz.open()
                    single_page_doc.insert_pdf(source_doc, from_page=page_num, to_page=page_num)
                    single_page_bytes = single_page_doc.write()
                    single_page_doc.close()
                    
                    # 1-based 페이지 번호로 저장
                    self.page_data[page_num + 1] = single_page_bytes
                    
                    if (page_num + 1) % 10 == 0:
                        print(f"Created page data: {page_num + 1}/{self.total_pages}")
                    
                except Exception as e:
                    print(f"Error creating page data for page {page_num + 1}: {str(e)}")
                    self.page_data[page_num + 1] = None
            
            source_doc.close()
            print(f"Page data creation completed: {len(self.page_data)} pages")
            return True
            
        except Exception as e:
            print(f"Error in create_page_data: {str(e)}")
            return False
    
    def process_single_page(self, page_num: int) -> Dict[str, Any]:
        """
        단일 페이지 처리 (기존 services 함수 재사용)
        
        Args:
            page_num: 페이지 번호 (1-based)
        
        Returns:
            Dict: 처리된 페이지 데이터
        """
        try:
            print(f"Processing page {page_num}...")
            
            # 페이지 PDF 바이트 가져오기
            page_pdf_bytes = self.page_data.get(page_num)
            if not page_pdf_bytes:
                raise ValueError(f"No PDF data for page {page_num}")
            
            # 1. 기존 convert_pdf_page_to_base64 함수 사용
            image_url = convert_pdf_page_to_base64(page_pdf_bytes)
            if not image_url:
                raise ValueError("Failed to convert page to base64")
            
            # data: URL 형식으로 변환
            if not image_url.startswith('data:'):
                image_url = f"data:image/png;base64,{image_url}"
            
            # 2. 기존 analyze_image 함수 사용 (가드레일 우회 프롬프트)
            sys = """Your task is to interpret the unstructured text as precisely as possible and convert it into well-organized, readable format.
            Since the text may be recognized from incomplete OCR engine, the order and structure of the original text may be mixed up, and there may be some potential typos.
            Identify all text elements, paragraphs, headings, lists, tables, or any textual content mentioned in the image and extract them accurately.
            Preserve the original language and structure as much as possible. Do not translate or modify the content unnecessarily.
            The resulting output should provide clear, structured information exactly as presented in the original document.
            """
            analysis_request = ImageAnalysisRequest(
                image_url=image_url,
                prompt=f"{sys} 해당 페이지 {page_num})의 텍스트를 정확하게 추출해주세요. 표, 목록, 제목 등의 구조를 유지하면서 읽기 쉽게 정리해주세요.",
                model="gpt-4o",
                max_tokens=1000
            )
            
            # 비동기 함수 동기적 호출
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            analysis_result = loop.run_until_complete(analyze_image(analysis_request))
            loop.close()
            
            text_content = analysis_result.response
            
            # 진행률 업데이트
            with self.lock:
                self.processed_pages += 1
            
            result = {
                'page_number': page_num,
                'text_content': text_content,
                'image_url': image_url,
                'file_name': self.filename,
                'processed_at': time.time(),
                'unique_id': f"{self.filename}_page_{page_num}",
                'success': True
            }
            
            print(f"Successfully processed page {page_num}")
            return result
            
        except Exception as e:
            print(f"Error processing page {page_num}: {str(e)}")
            
            with self.lock:
                self.processed_pages += 1
                
            return {
                'page_number': page_num,
                'text_content': f"Error processing page: {str(e)}",
                'image_url': None,
                'file_name': self.filename,
                'processed_at': time.time(),
                'unique_id': f"{self.filename}_page_{page_num}",
                'success': False,
                'error': str(e)
            }
    
    def process_batch(self, page_numbers: List[int]) -> List[Dict[str, Any]]:
        """
        배치 단위로 페이지들을 병렬 처리
        
        Args:
            page_numbers: 처리할 페이지 번호 리스트 (1-based)
        
        Returns:
            List[Dict]: 처리된 페이지 데이터 리스트
        """
        print(f"Processing batch: pages {page_numbers}")
        
        batch_results = []
        max_workers = min(len(page_numbers), 4)  # 최대 4개 워커
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 페이지별 처리 작업 제출
            futures = {
                executor.submit(self.process_single_page, page_num): page_num
                for page_num in page_numbers
            }
            
            print(f"Submitted {len(futures)} page processing tasks")
            
            # 완료되는 순서대로 결과 수집
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=60)  # 60초 타임아웃
                    batch_results.append(result)
                except Exception as e:
                    page_num = futures[future]
                    print(f"Error processing page {page_num}: {str(e)}")
                    
                    error_result = {
                        'page_number': page_num,
                        'text_content': f"Processing timeout or error: {str(e)}",
                        'success': False,
                        'error': str(e)
                    }
                    batch_results.append(error_result)
                    
                    with self.lock:
                        self.processed_pages += 1
        
        print(f"Batch completed: {len(batch_results)} pages processed")
        return batch_results
    
    def process_batch_streaming(self, page_numbers: List[int]):
        """
        배치 단위로 페이지들을 병렬 처리하면서 실시간 스트리밍
        완료되는 페이지마다 즉시 yield
        
        Args:
            page_numbers: 처리할 페이지 번호 리스트 (1-based)
        
        Yields:
            str: 완료된 페이지 텍스트 또는 상태 메시지
        """
        print(f"Processing batch: pages {page_numbers}")
        
        max_workers = min(len(page_numbers), 4)  # 최대 4개 워커
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 페이지별 처리 작업 제출
            futures = {
                executor.submit(self.process_single_page, page_num): page_num
                for page_num in page_numbers
            }
            
            print(f"Submitted {len(futures)} page processing tasks")
            
            # 완료되는 순서대로 결과 수집 및 실시간 스트리밍
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=60)  # 60초 타임아웃
                    page_num = result['page_number']
                    
                    if result['success']:
                        text_content = result['text_content']
                        # 즉시 스트리밍 출력
                        yield f"## 📄 페이지 {page_num}\n\n{text_content}\n\n---\n\n"
                    else:
                        error_msg = result.get('error', '알 수 없는 오류')
                        yield f"## ❌ 페이지 {page_num} 처리 실패\n\n오류: {error_msg}\n\n---\n\n"
                    
                except Exception as e:
                    page_num = futures[future]
                    print(f"Error processing page {page_num}: {str(e)}")
                    
                    with self.lock:
                        self.processed_pages += 1
                    
                    yield f"## ❌ 페이지 {page_num} 처리 중단\n\n오류: {str(e)}\n\n---\n\n"
        
        print(f"Batch completed: {len(page_numbers)} pages processed")

    def process_pdf_streaming(self):
        """
        PDF를 배치 단위로 처리하면서 실시간으로 결과를 스트리밍
        배치 내부에서도 페이지별 실시간 출력
        
        Yields:
            str: 처리된 페이지 텍스트 또는 상태 메시지
        """
        self.start_time = time.time()
        self.total_pages = self.get_total_pages()
        
        print(f"Starting PDF streaming processing: {self.total_pages} pages, batch size: {PDF_BATCH_SIZE}")
        
        if self.total_pages == 0:
            yield "❌ PDF에서 페이지를 찾을 수 없습니다."
            return
        
        yield f"📄 PDF 문서 분석을 시작합니다 (총 {self.total_pages}페이지)\n\n"
        
        # 1. 페이지 데이터 생성
        if not self.create_page_data():
            yield "❌ PDF 페이지 데이터 생성에 실패했습니다."
            return
        
        yield f"✅ 페이지 데이터 생성 완료\n\n"
        
        # 2. 배치별 처리 및 실시간 스트리밍
        batch_count = 0
        total_batches = (self.total_pages + PDF_BATCH_SIZE - 1) // PDF_BATCH_SIZE
        
        yield f"🔄 총 {total_batches}개 배치로 처리합니다\n\n"
        
        # 배치 단위로 순차 처리
        for batch_start in range(1, self.total_pages + 1, PDF_BATCH_SIZE):
            # 타임아웃 체크
            elapsed_time = time.time() - self.start_time
            if elapsed_time > PDF_PROCESSING_TIMEOUT:
                yield f"⏰ 처리 시간 초과 ({elapsed_time:.1f}초 > {PDF_PROCESSING_TIMEOUT}초)\n"
                yield f"지금까지 처리된 {self.processed_pages}페이지의 결과를 반환합니다.\n\n"
                break
            
            batch_end = min(batch_start + PDF_BATCH_SIZE - 1, self.total_pages)
            page_numbers = list(range(batch_start, batch_end + 1))
            batch_count += 1
            
            yield f"📋 배치 {batch_count}/{total_batches} 처리 중: 페이지 {batch_start}-{batch_end}\n\n"
            
            # 🆕 배치 내부 실시간 스트리밍 처리
            try:
                # 페이지별 실시간 결과를 그대로 전달
                for page_result in self.process_batch_streaming(page_numbers):
                    yield page_result
                
                yield f"✅ 배치 {batch_count} 완료\n\n"
                
            except Exception as e:
                print(f"Error processing batch {batch_count}: {str(e)}")
                yield f"❌ 배치 {batch_count} 처리 중 오류 발생: {str(e)}\n\n"
                break
        
        # 처리 완료 요약
        processing_time = time.time() - self.start_time
        completed = self.processed_pages >= self.total_pages
        
        yield f"## 📊 처리 완료 요약\n\n"
        yield f"- 총 페이지: {self.total_pages}페이지\n"
        yield f"- 처리 완료: {self.processed_pages}페이지\n"
        yield f"- 처리 시간: {processing_time:.1f}초\n"
        yield f"- 상태: {'✅ 완료' if completed else '⚠️ 부분 완료 (타임아웃)'}\n\n"
        
        print(f"\n=== PDF Streaming Processing Summary ===")
        print(f"Total pages processed: {self.processed_pages}/{self.total_pages}")
        print(f"Total processing time: {processing_time:.1f}s")
        print(f"Status: {'Completed' if completed else 'Partial (timeout)'}")

    def process_pdf_in_batches(self) -> Tuple[List[Dict[str, Any]], bool]:
        """
        PDF를 배치 단위로 처리 (기존 방식 - 호환성 유지)
        
        Returns:
            Tuple[List[Dict], bool]: (처리된 페이지 데이터 리스트, 완료 여부)
        """
        self.start_time = time.time()
        self.total_pages = self.get_total_pages()
        
        print(f"Starting PDF batch processing: {self.total_pages} pages, batch size: {PDF_BATCH_SIZE}")
        
        if self.total_pages == 0:
            print("No pages found in PDF")
            return [], False
        
        # 1. 페이지 데이터 생성
        if not self.create_page_data():
            print("Failed to create page data")
            return [], False
        
        # 2. 배치별 처리
        all_results = []
        batch_count = 0
        total_batches = (self.total_pages + PDF_BATCH_SIZE - 1) // PDF_BATCH_SIZE
        
        print(f"Total batches to process: {total_batches}")
        
        # 배치 단위로 순차 처리
        for batch_start in range(1, self.total_pages + 1, PDF_BATCH_SIZE):
            # 타임아웃 체크
            elapsed_time = time.time() - self.start_time
            if elapsed_time > PDF_PROCESSING_TIMEOUT:
                print(f"Processing timeout after {elapsed_time:.1f} seconds (limit: {PDF_PROCESSING_TIMEOUT}s)")
                break
            
            batch_end = min(batch_start + PDF_BATCH_SIZE - 1, self.total_pages)
            page_numbers = list(range(batch_start, batch_end + 1))
            batch_count += 1
            
            print(f"\n=== Batch {batch_count}/{total_batches}: Pages {batch_start}-{batch_end} ===")
            print(f"Elapsed time: {elapsed_time:.1f}s / {PDF_PROCESSING_TIMEOUT}s")
            
            # 배치 처리 실행
            try:
                batch_results = self.process_batch(page_numbers)
                all_results.extend(batch_results)
                
                print(f"Batch {batch_count} completed: {len(batch_results)} pages processed")
                
            except Exception as e:
                print(f"Error processing batch {batch_count}: {str(e)}")
                break
        
        # 완료 여부 확인
        completed = self.processed_pages >= self.total_pages
        processing_time = time.time() - self.start_time
        
        print(f"\n=== PDF Processing Summary ===")
        print(f"Total pages processed: {self.processed_pages}/{self.total_pages}")
        print(f"Total processing time: {processing_time:.1f}s")
        print(f"Batches processed: {batch_count}/{total_batches}")
        print(f"Status: {'Completed' if completed else 'Partial (timeout)'}")
        
        # 결과를 페이지 번호 순으로 정렬
        all_results.sort(key=lambda x: x.get('page_number', 0))
        
        return all_results, completed
    
    def get_progress(self) -> Dict[str, Any]:
        """현재 처리 진행률 반환"""
        return {
            'processed_pages': self.processed_pages,
            'total_pages': self.total_pages,
            'progress_percentage': (self.processed_pages / max(self.total_pages, 1)) * 100,
            'elapsed_time': time.time() - self.start_time if self.start_time else 0
        }
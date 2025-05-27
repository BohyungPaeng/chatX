# api/app/pdf_processor.py
"""
PDF 배치 처리 및 텍스트 추출
"""

import time
import fitz
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
from .services import analyze_image
from .models import ImageAnalysisRequest
import threading
import asyncio
import base64

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
    
    def split_pdf_to_batch(self, start_page: int, end_page: int) -> bytes:
        """
        PDF를 지정된 페이지 범위로 분할하여 배치용 PDF 바이트 생성
        
        Args:
            start_page: 시작 페이지 (0-based)
            end_page: 끝 페이지 (0-based, exclusive)
        
        Returns:
            bytes: 배치용 PDF 바이트 데이터
        """
        try:
            # 원본 PDF 열기
            source_doc = fitz.open(stream=self.pdf_content, filetype="pdf")
            
            # 새로운 PDF 문서 생성
            batch_doc = fitz.open()
            
            # 지정된 페이지 범위를 새 문서에 삽입
            batch_doc.insert_pdf(source_doc, from_page=start_page, to_page=end_page-1)
            
            # PDF 바이트로 변환
            batch_pdf_bytes = batch_doc.write()
            
            # 정리
            source_doc.close()
            batch_doc.close()
            
            print(f"Created batch PDF: pages {start_page+1}-{end_page} ({end_page-start_page} pages)")
            return batch_pdf_bytes
            
        except Exception as e:
            print(f"Error creating batch PDF for pages {start_page+1}-{end_page}: {str(e)}")
            raise e
    
    def convert_batch_pdf_to_base64_images(self, batch_pdf_bytes: bytes, batch_start_page: int) -> List[Dict[str, Any]]:
        """
        배치 PDF의 각 페이지를 base64 이미지로 변환
        
        Args:
            batch_pdf_bytes: 배치 PDF 바이트 데이터
            batch_start_page: 배치의 시작 페이지 번호 (0-based)
        
        Returns:
            List[Dict]: 페이지별 이미지 데이터 리스트
        """
        try:
            doc = fitz.open(stream=batch_pdf_bytes, filetype="pdf")
            page_images = []
            
            for page_idx in range(len(doc)):
                try:
                    # 페이지를 이미지로 변환 (300 DPI)
                    page = doc[page_idx]
                    matrix = fitz.Matrix(300/72, 300/72)
                    pix = page.get_pixmap(matrix=matrix)
                    img_bytes = pix.tobytes("png")
                    base64_image = base64.b64encode(img_bytes).decode('utf-8')
                    image_url = f"data:image/png;base64,{base64_image}"
                    
                    # 실제 페이지 번호 계산 (1-based)
                    actual_page_num = batch_start_page + page_idx + 1
                    
                    page_data = {
                        'page_number': actual_page_num,
                        'image_url': image_url,
                        'batch_index': page_idx,
                        'processed': False
                    }
                    page_images.append(page_data)
                    
                except Exception as e:
                    print(f"Error converting page {batch_start_page + page_idx + 1} to image: {str(e)}")
                    # 에러 페이지도 포함 (빈 이미지로)
                    actual_page_num = batch_start_page + page_idx + 1
                    page_data = {
                        'page_number': actual_page_num,
                        'image_url': None,
                        'batch_index': page_idx,
                        'processed': False,
                        'error': str(e)
                    }
                    page_images.append(page_data)
            
            doc.close()
            print(f"Converted {len(page_images)} pages to base64 images")
            return page_images
            
        except Exception as e:
            print(f"Error in batch PDF to base64 conversion: {str(e)}")
            return []
    
    def extract_text_from_page_image(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        단일 페이지 이미지에서 텍스트 추출
        
        Args:
            page_data: 페이지 이미지 데이터
        
        Returns:
            Dict: 처리된 페이지 데이터
        """
        page_num = page_data['page_number']
        image_url = page_data.get('image_url')
        
        try:
            if not image_url:
                raise ValueError("No image URL provided")
            
            # 기존 analyze_image 함수 활용하여 텍스트 추출
            analysis_request = ImageAnalysisRequest(
                image_url=image_url,
                prompt=f"이 PDF 페이지(페이지 {page_num})의 모든 텍스트를 정확하게 추출해주세요. 표, 목록, 제목 등의 구조를 유지하면서 읽기 쉽게 정리해주세요.",
                model="gpt-4o",
                max_tokens=1000
            )
            
            # 새로운 이벤트 루프에서 비동기 함수 실행
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                analysis_result = loop.run_until_complete(analyze_image(analysis_request))
                text_content = analysis_result.response
                loop.close()
            except Exception as async_error:
                print(f"Error in async analysis for page {page_num}: {str(async_error)}")
                text_content = f"텍스트 추출 실패: {str(async_error)}"
            
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
                'image_url': image_url,
                'file_name': self.filename,
                'processed_at': time.time(),
                'unique_id': f"{self.filename}_page_{page_num}",
                'success': False,
                'error': str(e)
            }
    
    def process_batch(self, batch_start_page: int, batch_end_page: int) -> List[Dict[str, Any]]:
        """
        배치 단위로 페이지들을 처리하는 함수
        
        Args:
            batch_start_page: 배치 시작 페이지 (0-based)
            batch_end_page: 배치 끝 페이지 (0-based, exclusive)
        
        Returns:
            List[Dict]: 처리된 페이지 데이터 리스트
        """
        print(f"Processing batch: pages {batch_start_page+1}-{batch_end_page}")
        
        try:
            # 1. 배치용 PDF 생성
            batch_pdf_bytes = self.split_pdf_to_batch(batch_start_page, batch_end_page)
            
            # 2. 배치 PDF의 각 페이지를 base64 이미지로 변환
            page_images = self.convert_batch_pdf_to_base64_images(batch_pdf_bytes, batch_start_page)
            
            if not page_images:
                print(f"No pages to process in batch {batch_start_page+1}-{batch_end_page}")
                return []
            
            # 3. ThreadPoolExecutor로 각 페이지 병렬 처리
            batch_results = []
            max_workers = min(len(page_images), 4)  # 최대 4개 워커
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 페이지별 텍스트 추출 작업 제출
                futures = {
                    executor.submit(self.extract_text_from_page_image, page_data): page_data
                    for page_data in page_images
                }
                
                print(f"Submitted {len(futures)} page processing tasks for batch")
                
                # 완료되는 순서대로 결과 수집
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)  # 개별 페이지 30초 타임아웃
                        batch_results.append(result)
                    except Exception as e:
                        page_data = futures[future]
                        page_num = page_data['page_number']
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
            
            print(f"Completed batch processing: {len(batch_results)} pages processed")
            return batch_results
            
        except Exception as e:
            print(f"Error in batch processing {batch_start_page+1}-{batch_end_page}: {str(e)}")
            return []
    
    def process_pdf_in_batches(self) -> Tuple[List[Dict[str, Any]], bool]:
        """
        PDF를 배치 단위로 처리
        1~8페이지 -> 9~16페이지 -> ... 순서로 배치 처리
        
        Returns:
            Tuple[List[Dict], bool]: (처리된 페이지 데이터 리스트, 완료 여부)
        """
        self.start_time = time.time()
        self.total_pages = self.get_total_pages()
        
        if self.total_pages == 0:
            return [], False
        
        print(f"Starting PDF batch processing: {self.total_pages} pages, batch size: {PDF_BATCH_SIZE}")
        print(f"Total batches to process: {(self.total_pages + PDF_BATCH_SIZE - 1) // PDF_BATCH_SIZE}")
        
        all_results = []
        batch_count = 0
        
        # 배치 단위로 순차 처리 (1~8, 9~16, 17~24, ...)
        for batch_start in range(0, self.total_pages, PDF_BATCH_SIZE):
            # 타임아웃 체크
            elapsed_time = time.time() - self.start_time
            if elapsed_time > PDF_PROCESSING_TIMEOUT:
                print(f"Processing timeout after {elapsed_time:.1f} seconds (limit: {PDF_PROCESSING_TIMEOUT}s)")
                break
            
            batch_end = min(batch_start + PDF_BATCH_SIZE, self.total_pages)
            batch_count += 1
            
            print(f"\n=== Batch {batch_count}: Pages {batch_start+1}-{batch_end} ===")
            print(f"Elapsed time: {elapsed_time:.1f}s / {PDF_PROCESSING_TIMEOUT}s")
            
            # 배치 처리 실행
            try:
                batch_results = self.process_batch(batch_start, batch_end)
                all_results.extend(batch_results)
                
                print(f"Batch {batch_count} completed: {len(batch_results)} pages processed")
                
            except Exception as e:
                print(f"Error processing batch {batch_count} (pages {batch_start+1}-{batch_end}): {str(e)}")
                break
        
        # 완료 여부 확인
        completed = self.processed_pages >= self.total_pages
        processing_time = time.time() - self.start_time
        
        print(f"\n=== PDF Processing Summary ===")
        print(f"Total pages processed: {self.processed_pages}/{self.total_pages}")
        print(f"Total processing time: {processing_time:.1f}s")
        print(f"Batches processed: {batch_count}")
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
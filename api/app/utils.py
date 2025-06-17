# api/app/utils.py
"""
범용 유틸리티 함수들
Services Layer와 동일한 층위
"""

import re

def calculate_language_score(text: str) -> float:
    """
    텍스트의 언어/의미 점수 계산
    1.0 = 완전히 읽을 수 있는 텍스트
    0.0 = 완전히 깨진/암호화된 텍스트
    """
    if not text.strip():
        return 0.0
    
    # 1. 한글/영문 문자 비율
    korean_chars = len(re.findall(r'[가-힣]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    numeric_chars = len(re.findall(r'[0-9]', text))
    total_meaningful = korean_chars + english_chars + numeric_chars
    
    if len(text) == 0:
        return 0.0
    
    meaningful_ratio = total_meaningful / len(text)
    
    # 2. 일반적인 단어 패턴 존재 여부
    common_patterns = [
        r'\b\w{2,}\b',  # 2글자 이상 단어
        r'[.!?]',       # 문장 부호
        r'\d+',         # 숫자
        r'[가-힣]{2,}', # 2글자 이상 한글
    ]
    
    pattern_score = 0
    for pattern in common_patterns:
        if re.search(pattern, text):
            pattern_score += 0.25
    
    # 3. 특수문자/이상한 문자 비율 (패널티)
    weird_chars = len(re.findall(r'[^\w\s가-힣.,!?()[\]{}:;"\'-]', text))
    weird_penalty = min(weird_chars / len(text), 0.5)  # 최대 0.5 패널티
    
    # 최종 점수 계산
    final_score = (meaningful_ratio * 0.6 + pattern_score * 0.4) - weird_penalty
    return max(0.0, min(1.0, final_score))


def detect_summary_request(query: str) -> tuple[bool, list[int]]:
    """요약 요청 감지 - 복수 페이지 지원"""    
    SUMMARY_KEYWORDS = [
        '요약', '전체', '개요', '주요 내용', '핵심', '전반적', '종합',
        'summary', 'summarize', 'overview', 'main points', 'key points', 'overall'
    ]
    query_lower = query.lower()
    is_summary = any(keyword in query_lower for keyword in SUMMARY_KEYWORDS)
        
    # 페이지 번호 추출 (다양한 패턴 + 복수 페이지 지원)
    page_patterns = [
        r'(\d+)\s*페이지',
        r'(\d+)\s*쪽',
        r'(\d+)\s*p\b',
        r'page\s*(\d+)',
        r'(\d+)번째\s*페이지'
    ]
    
    page_numbers = []
    for pattern in page_patterns:
        matches = re.finditer(pattern, query_lower)
        for match in matches:
            page_num = int(match.group(1))
            if page_num not in page_numbers:
                page_numbers.append(page_num)
    
    # 범위 패턴 지원 (예: "3-7페이지", "page 5 to 10")
    range_patterns = [
        r'(\d+)-(\d+)\s*페이지',
        r'(\d+)에서\s*(\d+)\s*페이지',
        r'page\s*(\d+)\s*to\s*(\d+)',
        r'(\d+)부터\s*(\d+)까지'
    ]
    
    for pattern in range_patterns:
        match = re.search(pattern, query_lower)
        if match:
            start_page = int(match.group(1))
            end_page = int(match.group(2))
            for page_num in range(start_page, end_page + 1):
                if page_num not in page_numbers:
                    page_numbers.append(page_num)
    
    page_numbers.sort()  # 정렬
    
    # 전체문서 모드: 요약 요청이면서 특정 페이지 지정 없음
    use_full_document = is_summary and len(page_numbers) == 0
    
    return use_full_document, page_numbers
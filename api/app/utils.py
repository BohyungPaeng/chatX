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
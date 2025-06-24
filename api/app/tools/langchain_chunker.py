from typing import List, Optional

class RecursiveCharacterTextSplitter:
    """재귀적 문자 기반 텍스트 분할기 (langchain 원본 기반)"""
    
    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        length_function: callable = len,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True,
    ):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = length_function
        self._keep_separator = keep_separator
        self._separators = separators or ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """텍스트를 재귀적으로 분할"""
        return self._split_text(text, self._separators)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """재귀적 분할 핵심 로직"""
        final_chunks = []
        separator = separators[-1]
        new_separators = []
        
        for i, _s in enumerate(separators):
            _separator = _s if self._keep_separator else ""
            if _s == "":
                separator = _separator
                break
            if _s in text:
                separator = _separator
                new_separators = separators[i + 1:]
                break

        splits = self._split_text_with_regex(text, separator, self._keep_separator)
        
        # 이제 적절한 크기의 청크들을 만들기
        _good_splits = []
        _separator = "" if self._keep_separator else separator
        
        for s in splits:
            if self._length_function(s) < self._chunk_size:
                _good_splits.append(s)
            else:
                if _good_splits:
                    merged_text = self._merge_splits(_good_splits, _separator)
                    final_chunks.extend(merged_text)
                    _good_splits = []
                if not new_separators:
                    final_chunks.append(s)
                else:
                    other_info = self._split_text(s, new_separators)
                    final_chunks.extend(other_info)
        
        if _good_splits:
            merged_text = self._merge_splits(_good_splits, _separator)
            final_chunks.extend(merged_text)
        
        return final_chunks

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """작은 분할들을 적절한 크기로 병합"""
        docs = []
        current_doc = []
        total = 0
        
        for d in splits:
            _len = self._length_function(d)
            if total + _len + (len(current_doc) * len(separator)) > self._chunk_size:
                if current_doc:
                    doc = self._join_docs(current_doc, separator)
                    if doc is not None:
                        docs.append(doc)
                    # overlap 처리
                    while (total > self._chunk_overlap or 
                           (total + _len + (len(current_doc) * len(separator)) > self._chunk_size and total > 0)):
                        total -= self._length_function(current_doc[0]) + (1 if len(current_doc) > 1 else 0) * len(separator)
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += _len + (1 if len(current_doc) > 1 else 0) * len(separator)
        
        doc = self._join_docs(current_doc, separator)
        if doc is not None:
            docs.append(doc)
        
        return docs

    def _join_docs(self, docs: List[str], separator: str) -> Optional[str]:
        """문서들을 구분자로 합치기"""
        text = separator.join(docs).strip()
        return text if text else None

    def _split_text_with_regex(self, text: str, separator: str, keep_separator: bool) -> List[str]:
        """정규식으로 텍스트 분할"""
        import re
        
        if separator:
            if keep_separator:
                splits = re.split(f"({re.escape(separator)})", text)
                splits = [splits[i] + splits[i + 1] for i in range(1, len(splits), 2)] if len(splits) > 1 else splits
            else:
                splits = text.split(separator)
        else:
            splits = list(text)
        
        return [s for s in splits if s != ""]
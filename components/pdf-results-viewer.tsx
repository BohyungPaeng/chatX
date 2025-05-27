"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronLeft, ChevronRight, FileText, Maximize2, Minimize2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PDFPage {
  pageNumber: number;
  textContent: string;
  success: boolean;
  error?: string;
}

interface PDFResultsViewerProps {
  fileName: string;
  pages: PDFPage[];
  isStreaming: boolean;
}

export function PDFResultsViewer({ fileName, pages, isStreaming }: PDFResultsViewerProps) {
  const [currentPage, setCurrentPage] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  
  // 새 페이지가 추가될 때마다 마지막 페이지로 스크롤
  useEffect(() => {
    if (isStreaming && pages.length > 0) {
      setCurrentPage(pages.length - 1);
    }
  }, [pages.length, isStreaming]);

  const validPages = pages.filter(page => page.success);
  const totalPages = validPages.length;

  if (pages.length === 0) return null;

  const handlePrevPage = () => {
    setCurrentPage(prev => Math.max(0, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage(prev => Math.min(totalPages - 1, prev + 1));
  };

  const currentPageData = validPages[currentPage];

  return (
    <div className={`border rounded-lg bg-gray-50 dark:bg-gray-900/50 transition-all duration-300 ${
      isExpanded ? 'fixed inset-4 z-50 bg-white dark:bg-gray-900' : 'max-h-96'
    }`}>
      {/* 헤더 */}
      <div className="flex items-center justify-between p-3 border-b bg-white dark:bg-gray-800 rounded-t-lg">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <span className="font-medium text-sm">📄 {fileName}</span>
          {isStreaming && (
            <span className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-full animate-pulse">
              처리 중...
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {totalPages > 0 ? `${currentPage + 1}/${totalPages} 페이지` : '0 페이지'}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-7 w-7"
          >
            {isExpanded ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
          </Button>
        </div>
      </div>

      {/* 내용 영역 */}
      <div 
        ref={scrollContainerRef}
        className={`overflow-auto ${isExpanded ? 'h-full p-4' : 'max-h-64 p-3'}`}
      >
        {totalPages > 0 && currentPageData ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              <span className="bg-blue-100 dark:bg-blue-900 px-2 py-1 rounded text-blue-700 dark:text-blue-300">
                페이지 {currentPageData.pageNumber}
              </span>
            </div>
            
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <div className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                {currentPageData.textContent}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-32 text-gray-500 dark:text-gray-400">
            {isStreaming ? (
              <div className="text-center">
                <div className="animate-spin h-6 w-6 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"></div>
                <p className="text-sm">PDF 페이지를 처리하고 있습니다...</p>
              </div>
            ) : (
              <p className="text-sm">처리된 페이지가 없습니다.</p>
            )}
          </div>
        )}
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 p-3 border-t bg-gray-50 dark:bg-gray-800/50">
          <Button
            variant="outline"
            size="sm"
            onClick={handlePrevPage}
            disabled={currentPage === 0}
            className="h-8"
          >
            <ChevronLeft className="h-3 w-3 mr-1" />
            이전
          </Button>
          
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              const pageIndex = totalPages <= 5 ? i : 
                currentPage < 3 ? i :
                currentPage > totalPages - 3 ? totalPages - 5 + i :
                currentPage - 2 + i;
              
              return (
                <Button
                  key={pageIndex}
                  variant={currentPage === pageIndex ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setCurrentPage(pageIndex)}
                  className="h-8 w-8 p-0 text-xs"
                >
                  {pageIndex + 1}
                </Button>
              );
            })}
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={handleNextPage}
            disabled={currentPage === totalPages - 1}
            className="h-8"
          >
            다음
            <ChevronRight className="h-3 w-3 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
"use client";

import { FileText, Clock, CheckCircle, AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

interface PDFProgressCardProps {
  fileName: string;
  totalPages: number;
  processedPages: number;
  isCompleted: boolean;
  isError: boolean;
  errorMessage?: string;
  processingTime?: number;
}

export function PDFProgressCard({
  fileName,
  totalPages,
  processedPages,
  isCompleted,
  isError,
  errorMessage,
  processingTime = 0
}: PDFProgressCardProps) {
  const [elapsed, setElapsed] = useState(processingTime);
  const progressPercentage = totalPages > 0 ? (processedPages / totalPages) * 100 : 0;

  useEffect(() => {
    if (!isCompleted && !isError) {
      const interval = setInterval(() => {
        setElapsed(prev => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [isCompleted, isError]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`p-4 rounded-lg border ${
      isError 
        ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' 
        : isCompleted 
        ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
        : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
    }`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-full ${
          isError 
            ? 'bg-red-100 dark:bg-red-800' 
            : isCompleted 
            ? 'bg-green-100 dark:bg-green-800'
            : 'bg-blue-100 dark:bg-blue-800'
        }`}>
          {isError ? (
            <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
          ) : isCompleted ? (
            <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
          ) : (
            <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          )}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-medium text-sm truncate">{fileName}</h4>
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
              <Clock className="h-3 w-3" />
              <span>{formatTime(elapsed)}</span>
            </div>
          </div>
          
          {!isError && (
            <>
              <div className="mb-2">
                <div className="flex justify-between text-xs text-gray-600 dark:text-gray-300 mb-1">
                  <span>진행률</span>
                  <span>{processedPages}/{totalPages} 페이지</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-500 ${
                      isCompleted 
                        ? 'bg-green-500' 
                        : 'bg-blue-500 animate-pulse'
                    }`}
                    style={{ width: `${Math.min(progressPercentage, 100)}%` }}
                  />
                </div>
              </div>
              
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {isCompleted 
                  ? '✅ PDF 분석이 완료되었습니다.' 
                  : '🔄 PDF를 페이지별로 분석하고 있습니다...'}
              </p>
            </>
          )}
          
          {isError && errorMessage && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              ❌ {errorMessage}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
"use client";

import React, { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Upload, X, FileText, Loader2 } from 'lucide-react';

interface FileUploadProps {
  onFileSelect: (files: File[]) => void;
}

export function FileUpload({ onFileSelect }: FileUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    
    if (files.length > 0) {
      // 파일 타입 검증
      const supportedTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain',
        'text/markdown',
        'text/csv'
      ];
      
      const validFiles = files.filter(file => {
        if (!supportedTypes.includes(file.type)) {
          alert(`${file.name}: 지원되지 않는 파일 형식입니다. PDF, DOCX, PPTX, TXT, MD, CSV 파일만 지원합니다.`);
          return false;
        }
        
        if (file.size > 100 * 1024 * 1024) { // 100MB
          alert(`${file.name}: 파일 크기가 너무 큽니다. 최대 100MB까지 지원합니다.`);
          return false;
        }
        
        return true;
      });
      
      if (validFiles.length > 0) {
        setSelectedFiles(prev => [...prev, ...validFiles]);
      }
      
      // 입력 초기화
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    
    setIsUploading(true);
    try {
      await onFileSelect(selectedFiles);
      setSelectedFiles([]); // 업로드 성공 시 선택된 파일 목록 초기화
    } catch (error) {
      console.error('파일 업로드 오류:', error);
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="group relative">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,.docx,.pptx,.txt,.md,.csv"
        multiple
        className="hidden"
      />
      
      <Button
        type="button"
        size="icon"
        variant="outline"
        onClick={handleFileSelect}
        disabled={isUploading}
        className="border-gray-200 dark:border-secondary hover:bg-gray-100 dark:hover:bg-secondary/80"
        title="파일 업로드 (PDF, DOCX, PPTX, TXT, MD, CSV)"
      >
        {isUploading ? (
          <Loader2 size={18} className="animate-spin" />
        ) : (
          <FileText size={18} />
        )}
        <span className="sr-only">Upload Files</span>
      </Button>
      
      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 p-2 bg-black text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
        파일 업로드 (PDF, DOCX, PPTX, TXT, MD, CSV) - 다중 선택 가능
      </div>
      
      {/* 선택된 파일 목록 */}
      {selectedFiles.length > 0 && (
        <div className="absolute bottom-full left-0 mb-2 p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg min-w-[300px] z-50">
          <div className="flex justify-between items-center mb-2">
            <h4 className="text-sm font-medium">선택된 파일 ({selectedFiles.length}개)</h4>
            <Button
              onClick={handleUpload}
              disabled={isUploading}
              size="sm"
              className="bg-orange-500 hover:bg-orange-600 text-white"
            >
              {isUploading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                "업로드"
              )}
            </Button>
          </div>
          
          <div className="max-h-40 overflow-y-auto space-y-1">
            {selectedFiles.map((file, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700 rounded text-xs">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <FileText size={14} className="text-gray-500 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{file.name}</div>
                    <div className="text-gray-500">{formatFileSize(file.size)}</div>
                  </div>
                </div>
                <Button
                  onClick={() => handleRemoveFile(index)}
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0 text-gray-400 hover:text-red-500"
                >
                  <X size={12} />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
} 
"use client";

import { Avatar } from "@/components/ui/avatar";
import { User, Bot, Copy, Check, Link } from "lucide-react";
import React, { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";

interface Citation {
  url?: string;
  title?: string;
  start_index?: number;
  end_index?: number;
  file_id?: string;
  filename?: string;
  type?: string;
  quote?: string;
  score?: number;
}

interface MessageProps {
  message: {
  id: number;
  role: "user" | "system";
  content: string;
  imageUrl?: string;
  citations?: Citation[];
  };
  isStreaming?: boolean;
  showImage?: boolean;
  className?: string;
}

// 테이블 컴포넌트
const TableComponent = ({ node, ...props }: any) => {
      return (
    <div className="overflow-x-auto">
      <table className="border-collapse border border-gray-300 dark:border-gray-700 w-full" {...props} />
        </div>
      );
};

const TableHead = (props: any) => <thead className="bg-gray-100 dark:bg-gray-800" {...props} />;
const TableRow = (props: any) => <tr className="border-b border-gray-300 dark:border-gray-700" {...props} />;
const TableCell = (props: any) => <td className="border border-gray-300 dark:border-gray-700 p-2" {...props} />;
const TableHeader = (props: any) => <th className="border border-gray-300 dark:border-gray-700 p-2 text-left" {...props} />;

// 코드 블록 컴포넌트
const PreBlock = ({ node, ...props }: any) => {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (node: any) => {
    // 텍스트 추출
    const text = node.children[0].children[0].value;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

    return (
    <div className="relative group">
      <pre
        {...props}
        className="bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 p-4 rounded-md overflow-auto border border-gray-200 dark:border-gray-700"
      />
      <button
        onClick={() => copyToClipboard(node)}
        className="absolute top-2 right-2 p-1 rounded-md text-gray-400 hover:text-gray-800 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
        aria-label="Copy code"
      >
        {copied ? (
          <Check size={18} />
        ) : (
          <Copy size={18} />
        )}
      </button>
    </div>
    );
};

export function ChatMessage({ message, isStreaming = false, showImage = true, className = "" }: MessageProps) {
  const [showCitations, setShowCitations] = useState(false);
  const isUser = message.role === "user";

  const toggleCitations = useCallback(() => {
    setShowCitations((prev) => !prev);
  }, []);

  // 인용 정보를 포함한 렌더링 함수
  const renderWithCitations = (content: string, citations: Citation[]) => {
    if (!citations || citations.length === 0) {
      return (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw, rehypeHighlight]}
          components={{
            pre: PreBlock,
            table: TableComponent,
            thead: TableHead,
            tr: TableRow,
            td: TableCell,
            th: TableHeader,
            strong: ({ node, children, ...props }) => (
              <strong className="font-bold" {...props}>
                {children}
              </strong>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      );
    }

    // Citation이 있는 경우도 마크다운으로 렌더링하되, 
    // 별도의 citation 정보는 하단에 표시
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeHighlight]}
        components={{
          pre: PreBlock,
          table: TableComponent,
          thead: TableHead,
          tr: TableRow,
          td: TableCell,
          th: TableHeader,
          strong: ({ node, children, ...props }) => (
            <strong className="font-bold" {...props}>
              {children}
            </strong>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    );
  };

  return (
    <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : ""}`}>
      <Avatar
        className={`flex items-center justify-center flex-shrink-0 ${
          isUser ? "bg-orange-500" : "bg-gray-700"
        }`}
      >
        {isUser ? (
          <User className="h-5 w-5 text-white" />
        ) : (
          <Bot className="h-5 w-5 text-white" />
        )}
      </Avatar>
      <div
        className={`flex-1 flex items-start ${
          isUser ? "justify-end" : "justify-start"
        } flex-col ${isUser ? "items-end" : "items-start"}`}
      >
        {isUser ? (
          <div className="text-gray-700 dark:text-foreground whitespace-pre-line text-right">
            {message.imageUrl && showImage && (
              <div
                className={`mb-2 ${isUser ? "ml-auto" : "mr-auto"} max-w-xs`}
              >
                <img
                  src={message.imageUrl}
                  alt="Uploaded image"
                  className="rounded-lg object-contain max-h-64 border border-gray-200 dark:border-gray-700 shadow-sm"
                />
              </div>
            )}
            {message.citations && message.citations.length > 0 ? (
              renderWithCitations(message.content, message.citations)
            ) : (
              message.content
            )}
          </div>
        ) : (
          <div className="w-full">
            <div
              className={`text-gray-700 dark:text-foreground prose dark:prose-invert 
              prose-headings:font-semibold
              prose-a:text-orange-500 dark:prose-a:text-orange-400
              prose-a:hover:text-orange-600 dark:prose-a:hover:text-orange-300
              prose-p:my-2
              prose-li:my-0.5
              prose-pre:bg-gray-100 dark:prose-pre:bg-gray-800 prose-pre:border prose-pre:border-gray-200 dark:prose-pre:border-gray-700
              prose-pre:shadow-sm
              prose-table:border-collapse prose-table:w-full
              prose-th:bg-gray-100 dark:prose-th:bg-gray-800 prose-th:p-2 prose-th:text-left
              prose-td:border prose-td:p-2 prose-td:border-gray-200 dark:prose-td:border-gray-700
              max-w-none ${isUser ? "text-right" : "text-left"}`}
            >
              {renderWithCitations(message.content, message.citations || [])}
              {isStreaming && <span className="animate-pulse">▌</span>}
            </div>

            {/* 인용 정보 표시 부분 */}
            {message.citations && message.citations.length > 0 && (
              <div className="mt-3 w-full">
                <div className="flex items-center gap-2">
                  <button
                    onClick={toggleCitations}
                    className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-orange-500 dark:hover:text-orange-400"
                  >
                    <Link size={14} />
                    {showCitations ? "인용 정보 숨기기" : "인용 정보 보기"} (
                    {message.citations.length})
                  </button>
                </div>

                {showCitations && (
                  <div className="mt-1 space-y-1 text-sm text-gray-600 dark:text-gray-300">
                    {message.citations.map((citation, index) => (
                      <div
                        key={index}
                        className="flex items-start gap-2 py-1 px-2 bg-gray-50 dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700"
                      >
                        <span className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          [{index + 1}]
                        </span>
                        <div className="flex-1">
                          {citation.url ? (
                            <>
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-orange-500 dark:text-orange-400 hover:underline"
                          >
                            {citation.title || citation.url}
                          </a>
                          <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {citation.url}
                          </div>
                            </>
                          ) : citation.file_id ? (
                            <>
                              <div className="flex items-center justify-between">
                                <span className="text-blue-500 dark:text-blue-400">
                                  {citation.filename || "업로드된 파일"}
                                </span>
                                {citation.score && (
                                  <span className="text-xs text-gray-400 ml-2">
                                    검색 점수: {(citation.score * 100).toFixed(1)}%
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                                파일 ID: {citation.file_id.substring(0, 15)}...
                              </div>
                              {citation.quote && (
                                <div className="text-xs text-gray-600 dark:text-gray-300 mt-2 p-3 bg-gray-100 dark:bg-gray-700 rounded">
                                  <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-1">
                                    📄 원본 소스 텍스트:
                                  </div>
                                  <div className="italic text-gray-600 dark:text-gray-400 border-l-2 border-blue-300 dark:border-blue-600 pl-3 max-h-32 overflow-y-auto text-sm leading-relaxed">
                                    "{citation.quote.length > 600 ? citation.quote.substring(0, 600) + "..." : citation.quote}"
                                  </div>
                                </div>
                              )}
                            </>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

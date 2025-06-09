import { Avatar } from "@/components/ui/avatar";
import { User, Bot, Copy, Check, Link } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeHighlight from "rehype-highlight";
import React, { useState, useRef, useCallback, ReactNode } from "react";
import { PDFProgressCard } from "@/components/pdf-progress-card";
import { PDFResultsViewer } from "@/components/pdf-results-viewer";
import { PDFGreetingMessage } from "@/components/pdf-greeting-message";

export interface Citation {
  url: string;
  title: string;
  start_index: number;
  end_index: number;
}

export interface PDFPage {
  pageNumber: number;
  textContent: string;
  success: boolean;
  error?: string;
}

export interface PDFProgress {
  fileName: string;
  totalPages: number;
  processedPages: number;
  isCompleted: boolean;
  isError: boolean;
  errorMessage?: string;
  processingTime?: number;
}

export interface Message {
  id: number;
  role: "user" | "system";
  content: string;
  imageUrl?: string;
  citations?: Citation[];
  pdfProgress?: PDFProgress;
  pdfPages?: PDFPage[];
  messageType?: "normal" | "pdf-progress" | "pdf-results" | "pdf-greeting";
  isAutoMessage?: boolean;
  customAvatar?: string;
  fileName?: string;
  onMasterSettingSubmit?: (prompt: string) => void;
}

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
  showImage?: boolean;
  customAvatar?: string;
}

export function ChatMessage({
  message,
  isStreaming = false,
  showImage = false,
  customAvatar,
}: ChatMessageProps) {
  const isUser = message.role === "user";
  const [copiedMap, setCopiedMap] = useState<Record<string, boolean>>({});
  const [showCitations, setShowCitations] = useState<boolean>(true);

  const copyToClipboard = useCallback((text: string, id: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedMap((prev) => ({ ...prev, [id]: true }));
      setTimeout(() => {
        setCopiedMap((prev) => ({ ...prev, [id]: false }));
      }, 2000);
    });
  }, []);

  // 코드 내용을 추출하는 함수
  const extractCodeText = useCallback((node: any): string => {
    if (!node) return "";

    // 문자열인 경우 바로 반환
    if (typeof node === "string") return node;

    // props와 children이 있는 객체인 경우 재귀적으로 처리
    if (typeof node === "object") {
      // props.children이 있는 경우
      if ("props" in node && node.props && node.props.children) {
        const children = node.props.children;

        // children이 배열인 경우
        if (Array.isArray(children)) {
          return children.map(extractCodeText).join("");
        }

        // children이 객체나 문자열인 경우
        return extractCodeText(children);
      }
    }

    return "";
  }, []);

  const PreBlock = useCallback(
    ({ children, ...props }: any) => {
      const preRef = useRef<HTMLPreElement>(null);
      const codeId = `code-${Math.random().toString(36).substr(2, 9)}`;
      const codeText = extractCodeText(children);
      const isCopied = copiedMap[codeId] || false;

      return (
        <div className="code-block-wrapper">
          <button
            className={`code-copy-button ${isCopied ? "copied" : ""}`}
            onClick={() => copyToClipboard(codeText, codeId)}
            aria-label="코드 복사"
            title="코드 복사"
          >
            <span className="flex items-center gap-1">
              {isCopied ? (
                <>
                  <Check size={14} />
                  <span className="text-xs">복사됨</span>
                </>
              ) : (
                <>
                  <Copy size={14} />
                  <span className="text-xs">복사</span>
                </>
              )}
            </span>
          </button>
          <pre ref={preRef} {...props}>
            {children}
          </pre>
        </div>
      );
    },
    [copiedMap, copyToClipboard, extractCodeText]
  );

  const TableComponent = useCallback(({ children, ...props }: any) => {
    return (
      <div className="overflow-x-auto my-4">
        <table className="border-collapse w-full" {...props}>
          {children}
        </table>
      </div>
    );
  }, []);

  const TableHead = useCallback(({ children, ...props }: any) => {
    return (
      <thead className="bg-gray-100 dark:bg-gray-800" {...props}>
        {children}
      </thead>
    );
  }, []);

  const TableRow = useCallback(({ children, ...props }: any) => {
    return (
      <tr
        className="border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
        {...props}
      >
        {children}
      </tr>
    );
  }, []);

  const TableCell = useCallback(({ children, ...props }: any) => {
    return (
      <td
        className="py-2 px-4 border-x border-gray-200 dark:border-gray-700"
        {...props}
      >
        {children}
      </td>
    );
  }, []);

  const TableHeader = useCallback(({ children, ...props }: any) => {
    return (
      <th
        className="py-3 px-4 text-left font-medium border-x border-gray-200 dark:border-gray-700"
        {...props}
      >
        {children}
      </th>
    );
  }, []);

  const toggleCitations = useCallback(() => {
    setShowCitations((prev) => !prev);
  }, []);

  // 스타일 객체 정의
  const getAvatarContent = () => {
    const avatarSrc = message.customAvatar || customAvatar;
    
    if (avatarSrc) {
      return (
        <img 
          src={avatarSrc} 
          alt="Custom Avatar" 
          className="h-8 w-8 rounded-lg object-cover"
        />
      );
    }
    
    return isUser ? (
      <User className="h-6 w-6 text-white" />
    ) : (
      <Bot className="h-6 w-6 text-white" />
    );
  };

  const messageStyles = {
    container: `flex gap-4 ${isUser ? "flex-row-reverse" : ""}`,
    avatar: `flex items-center justify-center flex-shrink-0 h-10 w-10 rounded-lg ${isUser ? "bg-orange-500" : "bg-gray-700"} ${message.customAvatar || customAvatar ? "p-0" : ""}`,
    messageContent: `flex-1 flex items-start ${isUser ? "justify-end" : "justify-start"} flex-col ${isUser ? "items-end" : "items-start"}`,
    userMessage: "text-gray-700 dark:text-foreground whitespace-pre-line text-right",
    imageContainer: `mb-2 ${isUser ? "ml-auto" : "mr-auto"} max-w-xs`,
    image: "rounded-lg object-contain max-h-64 border border-gray-200 dark:border-gray-700 shadow-sm",
    systemContainer: "w-full",
    pdfCardContainer: "mb-4",
    proseContainer: `text-gray-700 dark:text-foreground prose dark:prose-invert prose-headings:font-semibold prose-a:text-orange-500 dark:prose-a:text-orange-400 prose-a:hover:text-orange-600 dark:prose-a:hover:text-orange-300 prose-p:my-2 prose-li:my-0.5 prose-pre:bg-gray-100 dark:prose-pre:bg-gray-800 prose-pre:border prose-pre:border-gray-200 dark:prose-pre:border-gray-700 prose-pre:shadow-sm prose-table:border-collapse prose-table:w-full prose-th:bg-gray-100 dark:prose-th:bg-gray-800 prose-th:p-2 prose-th:text-left prose-td:border prose-td:p-2 prose-td:border-gray-200 dark:prose-td:border-gray-700 max-w-none ${isUser ? "text-right" : "text-left"}`,
    citationsContainer: "mt-3 w-full",
    citationButton: "flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-orange-500 dark:hover:text-orange-400",
    citationsList: "mt-1 space-y-1 text-sm text-gray-600 dark:text-gray-300",
    citationItem: "flex items-start gap-2 py-1 px-2 bg-gray-50 dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700",
    citationIndex: "text-xs text-gray-500 dark:text-gray-400 mt-0.5",
    citationLink: "text-orange-500 dark:text-orange-400 hover:underline",
    citationUrl: "text-xs text-gray-500 dark:text-gray-400 truncate"
  };

  return (
    <div className={messageStyles.container}>
      <Avatar className={messageStyles.avatar}>
        {getAvatarContent()}
      </Avatar>
      
      <div className={messageStyles.messageContent}>
        {isUser ? (
          <div className={messageStyles.userMessage}>
            {message.imageUrl && showImage && (
              <div className={messageStyles.imageContainer}>
                <img
                  src={message.imageUrl}
                  alt="Uploaded image"
                  className={messageStyles.image}
                />
              </div>
            )}
            {message.content}
          </div>
        ) : (
          <div className={messageStyles.systemContainer}>
            {/* PDF Progress Card */}
            {message.messageType === "pdf-progress" && message.pdfProgress && (
              <div className={messageStyles.pdfCardContainer}>
                <PDFProgressCard
                  fileName={message.pdfProgress.fileName}
                  totalPages={message.pdfProgress.totalPages}
                  processedPages={message.pdfProgress.processedPages}
                  isCompleted={message.pdfProgress.isCompleted}
                  isError={message.pdfProgress.isError}
                  errorMessage={message.pdfProgress.errorMessage}
                  processingTime={message.pdfProgress.processingTime}
                />
              </div>
            )}

            {/* PDF Results Viewer */}
            {message.messageType === "pdf-results" && message.pdfPages && (
              <div className={messageStyles.pdfCardContainer}>
                <PDFResultsViewer
                  fileName={message.pdfProgress?.fileName || "PDF 문서"}
                  pages={message.pdfPages}
                  isStreaming={isStreaming}
                />
              </div>
            )}

            {/* PDF 인사 메시지 */}
            {message.messageType === "pdf-greeting" && message.fileName && (
              <div className={messageStyles.systemContainer}>
                <PDFGreetingMessage 
                  fileName={message.fileName}
                  iconSrc={message.customAvatar || customAvatar}
                  onMasterSettingSubmit={message.onMasterSettingSubmit}
                />
              </div>
            )}
            {/* 일반 텍스트 메시지 */}
            {(!message.messageType || message.messageType === "normal") && message.content && (
              <div className={messageStyles.proseContainer}>
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
                  {message.content}
                </ReactMarkdown>
                {isStreaming && <span className="animate-pulse">▌</span>}
              </div>
            )}

            {/* 인용 정보 */}
            {message.citations && message.citations.length > 0 && (
              <div className={messageStyles.citationsContainer}>
                <div className="flex items-center gap-2">
                  <button
                    onClick={toggleCitations}
                    className={messageStyles.citationButton}
                  >
                    <Link size={14} />
                    {showCitations ? "인용 정보 숨기기" : "인용 정보 보기"} (
                    {message.citations.length})
                  </button>
                </div>

                {showCitations && (
                  <div className={messageStyles.citationsList}>
                    {message.citations.map((citation, index) => (
                      <div key={index} className={messageStyles.citationItem}>
                        <span className={messageStyles.citationIndex}>
                          [{index + 1}]
                        </span>
                        <div className="flex-1">
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noreferrer"
                            className={messageStyles.citationLink}
                          >
                            {citation.title || citation.url}
                          </a>
                          <div className={messageStyles.citationUrl}>
                            {citation.url}
                          </div>
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
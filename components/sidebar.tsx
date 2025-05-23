"use client";

import { Button } from "@/components/ui/button";
import {
  PlusCircle,
  MessageSquare,
  Settings,
  User,
  LogOut,
  ChevronLeft,
  ChevronRight,
  X,
  Edit3,
  MoreHorizontal,
} from "lucide-react";
import { useMobile } from "@/hooks/use-mobile";
import { useTheme } from "next-themes";
import Image from "next/image";
import { useEffect, useState, useRef } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// 채팅 히스토리 타입 정의
interface ChatHistory {
  id: number;
  title: string;
  lastMessage: string;
  timestamp: Date;
}

interface SidebarProps {
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({
  onClose,
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const isMobile = useMobile();
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // 채팅 히스토리 상태 추가
  const [chatHistory, setChatHistory] = useState<ChatHistory[]>([]);

  // 채팅 편집 상태 관리
  const [editingChatId, setEditingChatId] = useState<number | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const editInputRef = useRef<HTMLInputElement>(null);

  // useEffect only runs on the client, so now we can safely show the UI
  useEffect(() => {
    setMounted(true);
  }, []);

  // 채팅 히스토리 업데이트 이벤트 리스너 추가
  useEffect(() => {
    const handleChatHistoryUpdated = (event: CustomEvent) => {
      setChatHistory(event.detail.chatHistory);
    };

    // 이벤트 리스너 등록
    window.addEventListener(
      "chatHistoryUpdated",
      handleChatHistoryUpdated as EventListener
    );

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener(
        "chatHistoryUpdated",
        handleChatHistoryUpdated as EventListener
      );
    };
  }, []);

  // 채팅 클릭 핸들러
  const handleChatClick = (chat: ChatHistory) => {
    // 채팅 전환 이벤트 발송
    const event = new CustomEvent("switchChat", {
      detail: { chat },
    });
    window.dispatchEvent(event);
  };

  // 채팅 제목 편집 시작
  const startEditingTitle = (chat: ChatHistory) => {
    setEditingChatId(chat.id);
    setEditingTitle(chat.title);
    setTimeout(() => {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }, 10);
  };

  // 채팅 제목 편집 완료
  const finishEditingTitle = () => {
    if (editingChatId && editingTitle.trim()) {
      // 제목 업데이트 이벤트 발송
      const event = new CustomEvent("updateChatTitle", {
        detail: { chatId: editingChatId, newTitle: editingTitle.trim() },
      });
      window.dispatchEvent(event);
    }
    setEditingChatId(null);
    setEditingTitle("");
  };

  // 채팅 제목 편집 취소
  const cancelEditingTitle = () => {
    setEditingChatId(null);
    setEditingTitle("");
  };

  // 채팅 제목 편집 키보드 이벤트
  const handleTitleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      finishEditingTitle();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEditingTitle();
    }
  };

  // 채팅 삭제 핸들러
  const handleDeleteChat = (chatId: number, chatTitle: string) => {
    // 채팅 삭제 이벤트 발송 (confirm 제거)
    const event = new CustomEvent("deleteChat", {
      detail: { chatId, chatTitle },
    });
    window.dispatchEvent(event);
  };

  if (!mounted) {
    return (
      <div className="h-full flex flex-col bg-gray-100">
        {/* Loading placeholder */}
      </div>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <div
      className={`h-full flex flex-col ${
        isDark ? "bg-black text-white" : "bg-gray-100 text-gray-700"
      }`}
    >
      <div className="p-3 flex justify-between items-center">
        {!collapsed && (
          <>
            <div className="flex items-center gap-2">
              <div className="relative h-14 w-14">
                <Image
                  src={isDark ? "/pwc_logo_dark.png" : "/pwc_logo_light.png"}
                  alt="PwC Logo"
                  fill
                  className="object-contain"
                />
              </div>
              <h1
                className="text-3xl font-extrabold bg-gradient-to-r from-orange-500 via-orange-400 to-yellow-300 bg-clip-text text-transparent select-none drop-shadow-md"
              >
                Chat <span className="font-extrabold">X</span>
              </h1>
            </div>
            {!isMobile && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleCollapse}
                className={`h-8 w-8 ${
                  isDark
                    ? "text-white hover:bg-zinc-800"
                    : "text-gray-700 hover:bg-gray-200"
                }`}
              >
                <ChevronLeft size={16} />
                <span className="sr-only">Collapse sidebar</span>
              </Button>
            )}
          </>
        )}

        {collapsed && !isMobile && (
          <div className="mx-auto">
            <div className="relative h-14 w-14">
              <Image
                src={isDark ? "/pwc_logo_dark.png" : "/pwc_logo_light.png"}
                alt="PwC Logo"
                fill
                className="object-contain"
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleCollapse}
              className={`mt-2 h-8 w-8 ${
                isDark
                  ? "text-white hover:bg-zinc-800"
                  : "text-gray-700 hover:bg-gray-200"
              }`}
            >
              <ChevronRight size={16} />
              <span className="sr-only">Expand sidebar</span>
            </Button>
          </div>
        )}

        {isMobile && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className={`ml-auto h-8 w-8 ${
              isDark
                ? "text-white hover:bg-zinc-800"
                : "text-gray-700 hover:bg-gray-200"
            }`}
          >
            <span className="sr-only">Close sidebar</span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="lucide lucide-x"
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </Button>
        )}
      </div>

      {!collapsed && (
        <>
          <div className="p-3">
            <Button
              className={`w-full justify-start gap-2 ${
                isDark
                  ? "bg-zinc-800 text-white hover:bg-zinc-700 border-zinc-700"
                  : "bg-white text-gray-700 hover:bg-gray-50 border-gray-200"
              }`}
              variant="outline"
              onClick={() => {
                // 전역 이벤트 발생
                const newChatEvent = new CustomEvent("newChat");
                window.dispatchEvent(newChatEvent);
              }}
            >
              <PlusCircle size={16} />
              New Chat
            </Button>
          </div>

          <div className="flex-1 overflow-auto p-3">
            <div className="space-y-2">
              <h2
                className={`text-xs font-semibold uppercase tracking-wider mb-2 ${
                  isDark ? "text-zinc-400" : "text-gray-500"
                }`}
              >
                Recent Chats
              </h2>
              {chatHistory.length > 0 ? (
                chatHistory.map((chat) => (
                  <div
                    key={chat.id}
                    className={`group relative flex items-center w-full ${
                      isDark
                        ? "hover:bg-zinc-800"
                        : "hover:bg-gray-200"
                    } rounded-md overflow-hidden`}
                  >
                    {editingChatId === chat.id ? (
                      // 편집 모드
                      <div className="flex-1 px-2 py-1 min-w-0">
                        <input
                          ref={editInputRef}
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={handleTitleEditKeyDown}
                          onBlur={finishEditingTitle}
                          className={`w-full text-sm bg-transparent border border-gray-300 dark:border-gray-600 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-orange-500 ${
                            isDark ? "text-white" : "text-gray-700"
                          }`}
                          maxLength={50}
                        />
                      </div>
                    ) : (
                      // 일반 모드
                      <>
                        <Button
                          variant="ghost"
                          className={`flex-1 justify-start gap-2 h-auto py-2 px-2 pr-8 min-w-0 ${
                            isDark
                              ? "text-white hover:bg-transparent"
                              : "text-gray-700 hover:bg-transparent"
                          }`}
                          onClick={() => handleChatClick(chat)}
                        >
                          <MessageSquare size={16} className="shrink-0" />
                          <div className="flex flex-col items-start min-w-0 flex-1 overflow-hidden">
                            <span className="text-sm font-medium w-full text-left leading-tight truncate block">
                              {chat.title}
                            </span>
                            <span className="text-xs text-gray-500 dark:text-gray-400 w-full text-left leading-tight truncate block">
                              {chat.lastMessage}
                            </span>
                          </div>
                        </Button>

                        {/* 편집/삭제 드롭다운 - 호버 시에만 표시되도록 개선 */}
                        <div className="absolute top-1/2 right-2 transform -translate-y-1/2 shrink-0">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className={`h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-all duration-200 rounded-full ${
                                  isDark
                                    ? "text-gray-400 hover:text-white hover:bg-zinc-700"
                                    : "text-gray-400 hover:text-gray-700 hover:bg-gray-300"
                                }`}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <MoreHorizontal size={12} />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-32">
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  startEditingTitle(chat);
                                }}
                                className="cursor-pointer"
                              >
                                <Edit3 size={14} className="mr-2" />
                                편집
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteChat(chat.id, chat.title);
                                }}
                                className="cursor-pointer text-red-600 focus:text-red-600"
                              >
                                <X size={14} className="mr-2" />
                                삭제
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </>
                    )}
                  </div>
                ))
              ) : (
                <div
                  className={`text-sm ${
                    isDark ? "text-zinc-400" : "text-gray-500"
                  } py-2`}
                >
                  대화 기록이 없습니다
                </div>
              )}
            </div>
          </div>

          <div
            className={`p-3 border-t ${
              isDark ? "border-zinc-800" : "border-gray-200"
            }`}
          >
            <div className="space-y-2">
              <Button
                variant="ghost"
                className={`w-full justify-start gap-2 ${
                  isDark
                    ? "text-white hover:bg-zinc-800"
                    : "text-gray-700 hover:bg-gray-200"
                }`}
              >
                <User size={16} />
                Profile
              </Button>
              <Button
                variant="ghost"
                className={`w-full justify-start gap-2 ${
                  isDark
                    ? "text-white hover:bg-zinc-800"
                    : "text-gray-700 hover:bg-gray-200"
                }`}
              >
                <Settings size={16} />
                Settings
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start gap-2 text-red-500"
              >
                <LogOut size={16} />
                Logout
              </Button>
            </div>
          </div>
        </>
      )}

      {collapsed && !isMobile && (
        <>
          <div className="p-3 mt-2">
            <Button
              className={`w-full justify-center ${
                isDark
                  ? "bg-zinc-800 text-white hover:bg-zinc-700 border-zinc-700"
                  : "bg-white text-gray-700 hover:bg-gray-50 border-gray-200"
              }`}
              variant="outline"
              size="icon"
              onClick={() => {
                // 전역 이벤트 발생
                const newChatEvent = new CustomEvent("newChat");
                window.dispatchEvent(newChatEvent);
              }}
            >
              <PlusCircle size={16} />
              <span className="sr-only">New Chat</span>
            </Button>
          </div>

          <div className="flex-1 overflow-auto p-3">
            <div className="space-y-3 flex flex-col items-center">
              {chatHistory.length > 0 ? (
                chatHistory.map((chat) => (
                  <div
                    key={chat.id}
                    className="relative group"
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      className={`h-9 w-9 ${
                        isDark
                          ? "text-white hover:bg-zinc-800"
                          : "text-gray-700 hover:bg-gray-200"
                      }`}
                      onClick={() => handleChatClick(chat)}
                    >
                      <MessageSquare size={16} />
                      <span className="sr-only">{chat.title}</span>
                    </Button>
                    
                    {/* 호버 툴팁 - 더 나은 스타일링 */}
                    <div className="absolute left-full ml-2 px-3 py-2 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200 z-50 pointer-events-none w-64 max-w-xs">
                      <div className="font-medium text-white mb-1 truncate">
                        {chat.title}
                      </div>
                      <div className="text-xs text-gray-300 truncate">
                        {chat.lastMessage}
                      </div>
                      {/* 툴팁 화살표 */}
                      <div className="absolute top-1/2 left-0 transform -translate-y-1/2 -translate-x-1 w-2 h-2 bg-gray-900 dark:bg-gray-700 rotate-45"></div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-center text-gray-500 dark:text-gray-400 p-2">
                  No chats
                </div>
              )}
            </div>
          </div>

          <div
            className={`p-3 border-t ${
              isDark ? "border-zinc-800" : "border-gray-200"
            } flex flex-col items-center space-y-3`}
          >
            <Button
              variant="ghost"
              size="icon"
              className={`h-9 w-9 ${
                isDark
                  ? "text-white hover:bg-zinc-800"
                  : "text-gray-700 hover:bg-gray-200"
              }`}
            >
              <User size={16} />
              <span className="sr-only">Profile</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={`h-9 w-9 ${
                isDark
                  ? "text-white hover:bg-zinc-800"
                  : "text-gray-700 hover:bg-gray-200"
              }`}
            >
              <Settings size={16} />
              <span className="sr-only">Settings</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 text-red-500"
            >
              <LogOut size={16} />
              <span className="sr-only">Logout</span>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

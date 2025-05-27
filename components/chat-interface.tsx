"use client";

import { useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { ChatArea } from "@/components/chat-area";
import { useMobile } from "@/hooks/use-mobile";

export default function ChatInterface() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const isMobile = useMobile();

  return (
    <div className="flex h-screen bg-white dark:bg-background overflow-hidden">
      {/* Mobile overlay */}
      {isMobile && sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`${
          isMobile 
            ? sidebarOpen 
              ? "fixed left-0 top-0 bottom-0 z-50 w-64" 
              : "hidden"
            : sidebarOpen || !sidebarCollapsed
              ? sidebarCollapsed 
                ? "w-16" 
                : "w-64"
              : "w-0"
        } transition-all duration-300 ease-in-out border-r border-gray-200 dark:border-border flex-shrink-0`}
      >
        <Sidebar
          onClose={() => setSidebarOpen(false)}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      </div>

      {/* Main content - 레이아웃 안정화 */}
      <div className="flex-1 flex flex-col bg-white dark:bg-background min-w-0 overflow-hidden">
        <ChatArea
          onMenuClick={() =>
            isMobile
              ? setSidebarOpen(!sidebarOpen)
              : setSidebarCollapsed(!sidebarCollapsed)
          }
          sidebarOpen={sidebarOpen}
          sidebarCollapsed={sidebarCollapsed}
        />
      </div>
    </div>
  );
}
import { useState, useCallback } from "react";
import { PDFPage, PDFProgress, Message } from "@/components/chat-message";

export const usePDFProcessor = () => {
  const [pdfProcessing, setPdfProcessing] = useState<{
    fileName: string;
    totalPages: number;
    processedPages: number;
    startTime: number;
    pages: PDFPage[];
    progressMessageId: number | null;
    resultsMessageId: number | null;
  } | null>(null);

  const initializePDFProcessing = useCallback((fileName: string, progressId: number, resultsId: number) => {
    setPdfProcessing({
      fileName,
      totalPages: 0,
      processedPages: 0,
      startTime: Date.now(),
      pages: [],
      progressMessageId: progressId,
      resultsMessageId: resultsId
    });
  }, []);

  const processPDFContent = useCallback((content: string, setMessages: any) => {
    if (!pdfProcessing) return false;

    const pageMatch = content.match(/## 📄 페이지 (\d+)\n\n(.*?)(?=\n\n---|\n\n##|$)/s);
    if (pageMatch) {
      const pageNum = parseInt(pageMatch[1]);
      const pageContent = pageMatch[2];
      
      const newPage: PDFPage = {
        pageNumber: pageNum,
        textContent: pageContent,
        success: true
      };
      
      setPdfProcessing(prev => prev ? {
        ...prev,
        pages: [...prev.pages, newPage],
        processedPages: prev.processedPages + 1
      } : null);
      
      setMessages((currentMessages: Message[]) =>
        currentMessages.map((msg: Message) => {
          if (msg.id === pdfProcessing.progressMessageId && msg.pdfProgress) {
            return {
              ...msg,
              pdfProgress: {
                ...msg.pdfProgress,
                processedPages: pdfProcessing.processedPages + 1,
                processingTime: Math.floor((Date.now() - pdfProcessing.startTime) / 1000)
              }
            };
          }
          if (msg.id === pdfProcessing.resultsMessageId) {
            return {
              ...msg,
              pdfPages: [...pdfProcessing.pages, newPage]
            };
          }
          return msg;
        })
      );
      return true;
    }
    return false;
  }, [pdfProcessing]);

  const completePDFProcessing = useCallback((setMessages: any) => {
    if (!pdfProcessing) return;

    setMessages((currentMessages: Message[]) =>
      currentMessages.map((msg: Message) => {
        if (msg.id === pdfProcessing.progressMessageId && msg.pdfProgress) {
          return {
            ...msg,
            pdfProgress: {
              ...msg.pdfProgress,
              isCompleted: true,
              processingTime: Math.floor((Date.now() - pdfProcessing.startTime) / 1000)
            }
          };
        }
        return msg;
      })
    );
    setPdfProcessing(null);
  }, [pdfProcessing]);

  const handlePDFError = useCallback((errorMessage: string, setMessages: any) => {
    if (!pdfProcessing) return;

    setMessages((currentMessages: Message[]) =>
      currentMessages.map((msg: Message) => {
        if (msg.id === pdfProcessing.progressMessageId && msg.pdfProgress) {
          return {
            ...msg,
            pdfProgress: {
              ...msg.pdfProgress,
              isError: true,
              errorMessage
            }
          };
        }
        return msg;
      })
    );
    setPdfProcessing(null);
  }, [pdfProcessing]);

  return {
    pdfProcessing,
    initializePDFProcessing,
    processPDFContent,
    completePDFProcessing,
    handlePDFError
  };
};
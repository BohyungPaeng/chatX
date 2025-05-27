import { useCallback } from 'react';
const TIMEOUT_CONFIG = {
  DEFAULT: 30000,         // 30초
  PDF_PROCESSING: 240000  // 4분
};

export const useApiTimeout = () => {
  const getTimeoutDuration = useCallback((fileType?: string) => {
    return fileType === 'application/pdf' 
      ? TIMEOUT_CONFIG.PDF_PROCESSING 
      : TIMEOUT_CONFIG.DEFAULT;
  }, []);

  return { getTimeoutDuration };
};
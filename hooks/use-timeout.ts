import { useCallback } from 'react';
import { PROCESSING_CONFIG } from '../constants/processing-config';

export const useApiTimeout = () => {
  const getTimeoutDuration = useCallback((fileType?: string) => {
    const { API_TIMEOUTS } = PROCESSING_CONFIG;
    return fileType === 'application/pdf' 
      ? API_TIMEOUTS.PDF_PROCESSING  // 210초 (180 + 30)
      : API_TIMEOUTS.DEFAULT;        // 30초
  }, []);

  return { getTimeoutDuration };
};
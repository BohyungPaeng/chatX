export const PROCESSING_CONFIG = {
    // 백엔드와 동일한 값들
    PDF_BATCH_SIZE: 8,
    PDF_PROCESSING_TIMEOUT: 180, // 초 단위
    PDF_MAX_FILE_SIZE: 50 * 1024 * 1024,
    
    // 프론트엔드 전용
    TIMEOUT_BUFFER: 30, // 30초 버퍼
    
    // 계산된 값들
    get API_TIMEOUTS() {
      return {
        DEFAULT: 30000,
        PDF_PROCESSING: (this.TIMEOUT_BUFFER + this.PDF_PROCESSING_TIMEOUT) * 1000
      };
    }
  };
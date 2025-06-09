import { useState, useCallback } from "react";

interface ImageGenResult {
  iconSrc: string | null;
  loading: boolean;
  error: string | null;
}

/**
 * 파일명 기반 아이콘 생성 훅
 * /image-generation API 호출하여 base64 아이콘 반환
 */
export function useImageGeneration(): ImageGenResult & {
  generate: (filename: string, type?: string) => Promise<void>;
  clearIcon: () => void;
} {
  const [iconSrc, setIconSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(
    async (filename: string, type = "icon") => {
      setLoading(true);
      setError(null);
      
      try {
        console.log(`🎨 Generating icon for: ${filename}`);
        
        const formData = new FormData();
        formData.append("filename", filename);
        formData.append("type", type);

        // API_URL은 chat-area.tsx에서 정의된 상수와 동일하게 사용
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
        
        const response = await fetch(`${API_URL}/image-generation`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        
        if (!data.b64) {
          throw new Error("Invalid response: missing b64 data");
        }

        const iconDataUrl = `data:image/png;base64,${data.b64}`;
        setIconSrc(iconDataUrl);
        
        console.log("✅ Icon generated successfully");
        
      } catch (err) {
        console.error("❌ Icon generation failed:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const clearIcon = useCallback(() => {
    setIconSrc(null);
    setError(null);
    setLoading(false);
  }, []);

  return {
    iconSrc,
    loading,
    error,
    generate,
    clearIcon,
  };
}
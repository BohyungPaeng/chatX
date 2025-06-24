#############################################################
# 경량 배포환경에서 제한적으로 활용할 코드 snippet           
# miniLM같은 경량모델의 weight를 저장해놓고                  
# sentence-transformers 의존성없이 vector-search위한 코드
#############################################################

from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn.functional as F
import os

def mean_pool(last_hidden, attention_mask):           # ✔ 공식 가이드 방식
    mask = attention_mask.unsqueeze(-1).expand(last_hidden.size()).float()
    return (last_hidden * mask).sum(1) / torch.clamp(mask.sum(1), min=1e-9)
    # return torch.sum(last_hidden * mask, 1) / torch.clamp(mask.sum(1), min=1e-9)

def embed(texts, model_dir, device="cpu", pool="mean"):
    tok  = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    mdl  = AutoModel.from_pretrained(model_dir, local_files_only=True).to(device)
    batch = tok(texts, padding=True, truncation=True, return_tensors="pt").to(device)
    with torch.no_grad():
        out = mdl(**batch).last_hidden_state
    vec = mean_pool(out, batch["attention_mask"]) if pool=="mean" else out[:,0]  # CLS
    return F.normalize(vec, p=2, dim=1).cpu()

class LightweightEmbedder:
    def __init__(self, model_dir="models/all-MiniLM-L6-v2"):
        self.model_dir = model_dir
        print(f"🔍 절대경로: {os.path.abspath(self.model_dir)}")
        self.tokenizer = None
        self.model = None
        
    def load(self):
        """로컬 → 온라인 fallback으로 모델 로드"""
        # 1순위: 로컬 모델
        if os.path.exists(self.model_dir):
            try:
                print(f"🔍 로컬 모델 로드: {self.model_dir}")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir, local_files_only=True)
                self.model = AutoModel.from_pretrained(self.model_dir, local_files_only=True)
                print("✅ 로컬 로드 성공")
                return True
            except Exception as e:
                print(f"⚠️ 로컬 로드 실패: {e}")
        
        # 2순위: 온라인 다운로드 (transformers만 사용)
        try:
            print("🌐 온라인에서 all-MiniLM-L6-v2 다운로드...")
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            print("✅ 온라인 로드 성공")
            
            # 다운로드 성공시 로컬에 저장 (선택사항)
            if not os.path.exists(self.model_dir):
                os.makedirs(os.path.dirname(self.model_dir), exist_ok=True)
                self.tokenizer.save_pretrained(self.model_dir)
                self.model.save_pretrained(self.model_dir)
                print(f"💾 로컬에 저장: {self.model_dir}")
            
            return True
        except Exception as e:
            print(f"❌ 온라인 로드 실패: {e}")
            return False
    
    def encode(self, texts, device="cpu"):
        if not self.model:
            raise ValueError("Model not loaded")
        
        if isinstance(texts, str):
            texts = [texts]
            
        batch = self.tokenizer(texts, padding=True, truncation=True, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = self.model(**batch)
            
        embeddings = mean_pool(outputs.last_hidden_state, batch["attention_mask"])
        result = F.normalize(embeddings, p=2, dim=1).cpu().numpy()
        # 🔧 SentenceTransformer와 동일하게: 단일 텍스트면 1차원 반환
        if len(texts) == 1:
            return result[0]  # (1, 384) → (384,)
        else:
            return result     # (N, 384) 유지
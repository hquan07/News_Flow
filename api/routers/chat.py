import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from groq import Groq
from sentence_transformers import SentenceTransformer

from api.services.analytics import _query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    context_sources: list

# Lazy load models and clients
_embedding_model = None
_groq_client = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
    return _embedding_model

def get_groq_client():
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if api_key and api_key != "your_groq_api_key_here":
            _groq_client = Groq(api_key=api_key)
    return _groq_client

@router.post("", response_model=ChatResponse)
def ask_question(req: ChatRequest):
    model = get_embedding_model()
    groq_client = get_groq_client()
    
    if not model:
        raise HTTPException(status_code=500, detail="Embedding model not initialized.")
    if not groq_client:
        raise HTTPException(status_code=500, detail="Groq API key not configured.")
        
    try:
        # 1. Tạo vector cho câu hỏi
        question_vector = model.encode(req.message).tolist()
        
        # 2. Vector Search trong ClickHouse
        # Sử dụng cosineDistance (càng nhỏ càng giống nhau)
        sql = """
            SELECT 
                a.title as title,
                s.summary as summary,
                a.url as url,
                a.source as source,
                cosineDistance(e.embedding, {query_embedding:Array(Float32)}) AS distance
            FROM newspulse.raw_article_embeddings e
            JOIN newspulse.raw_article_summaries s ON e.url_hash = s.url_hash
            JOIN newspulse.raw_articles a ON e.url_hash = a.url_hash
            WHERE distance < 0.5
            ORDER BY distance ASC
            LIMIT 5
        """
        results = _query(sql, {"query_embedding": question_vector})
        
        if not results:
            return ChatResponse(
                answer="Xin lỗi, tôi không tìm thấy tin tức nào trong hệ thống phù hợp với câu hỏi của bạn.",
                context_sources=[]
            )
            
        # 3. Chuẩn bị Context cho LLM
        context_texts = []
        sources = []
        for i, row in enumerate(results):
            context_texts.append(f"[Bài báo {i+1}] Nguồn: {row['source']}\nTiêu đề: {row['title']}\nTóm tắt: {row['summary']}\nURL: {row['url']}")
            sources.append({"title": row['title'], "url": row['url'], "source": row['source']})
            
        combined_context = "\n\n".join(context_texts)
        
        # 4. Gọi Groq Llama-3 tạo câu trả lời
        prompt = f"""Bạn là trợ lý AI thông minh của hệ thống đọc báo NewsPulse.
Hãy trả lời câu hỏi của người dùng dựa vào CÁC BÀI BÁO (Context) bên dưới. 
Yêu cầu:
- Trả lời bằng tiếng Việt, văn phong tự nhiên, súc tích.
- Nếu thông tin trong Context không đủ để trả lời, hãy nói rõ là không có thông tin (không được tự bịa ra).
- Trích dẫn nguồn bài báo (Ví dụ: Theo [Bài báo 1]).

--- CONTEXT ---
{combined_context}

--- CÂU HỎI CỦA NGƯỜI DÙNG ---
{req.message}
"""
        
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama3-8b-8192",
            temperature=0.3,
            max_tokens=500,
        )
        
        answer = chat_completion.choices[0].message.content.strip()
        
        return ChatResponse(
            answer=answer,
            context_sources=sources
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

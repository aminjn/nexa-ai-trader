from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import json
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..ai.gapgpt import get_ai_response, stream_ai_response
from ..config import settings

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str


class MessageHistory(BaseModel):
    role: str
    content: str


@router.get("/chat/history")
async def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.user_id == current_user.id
    ).order_by(models.ChatMessage.created_at.desc()).limit(limit).all()
    messages.reverse()
    return [{
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at,
    } for m in messages]


@router.post("/chat")
async def send_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not settings.GAPGPT_API_KEY:
        raise HTTPException(status_code=400, detail="کلید API هوش مصنوعی تنظیم نشده است")

    # Save user message
    user_msg = models.ChatMessage(
        user_id=current_user.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    db.commit()

    # Get recent history for context
    history = db.query(models.ChatMessage).filter(
        models.ChatMessage.user_id == current_user.id
    ).order_by(models.ChatMessage.created_at.desc()).limit(20).all()
    history.reverse()

    messages = [{"role": m.role, "content": m.content} for m in history]

    # Get AI response
    response_text = await get_ai_response(messages)

    # Save assistant message
    asst_msg = models.ChatMessage(
        user_id=current_user.id,
        role="assistant",
        content=response_text,
    )
    db.add(asst_msg)
    db.commit()

    return {
        "role": "assistant",
        "content": response_text,
    }


@router.post("/chat/stream")
async def stream_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not settings.GAPGPT_API_KEY:
        raise HTTPException(status_code=400, detail="کلید API هوش مصنوعی تنظیم نشده است")

    user_msg = models.ChatMessage(
        user_id=current_user.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    db.commit()

    history = db.query(models.ChatMessage).filter(
        models.ChatMessage.user_id == current_user.id
    ).order_by(models.ChatMessage.created_at.desc()).limit(20).all()
    history.reverse()
    messages = [{"role": m.role, "content": m.content} for m in history]

    full_response = []

    async def generate():
        async for chunk in stream_ai_response(messages):
            full_response.append(chunk)
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        # Save complete response
        complete = "".join(full_response)
        asst_msg = models.ChatMessage(
            user_id=current_user.id,
            role="assistant",
            content=complete,
        )
        db.add(asst_msg)
        db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.put("/toggle-trading")
async def toggle_ai_trading(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    current_user.ai_trading_enabled = not current_user.ai_trading_enabled
    db.commit()
    return {"ai_trading_enabled": current_user.ai_trading_enabled}


@router.put("/api-key")
async def update_api_key(
    api_key: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین")
    settings.GAPGPT_API_KEY = api_key
    return {"message": "کلید API هوش مصنوعی ذخیره شد"}


@router.get("/connections")
async def get_ai_connections(
    current_user: models.User = Depends(get_current_user)
):
    """Returns AI provider connection status."""
    return [
        {
            "id": 1,
            "provider": "GapGPT (GPT-4o)",
            "status": "connected" if settings.GAPGPT_API_KEY else "disconnected",
        }
    ]


class ConnectionRequest(BaseModel):
    provider: str
    api_key: str


@router.post("/connections")
async def add_ai_connection(
    req: ConnectionRequest,
    current_user: models.User = Depends(get_current_user)
):
    """Save an AI provider API key."""
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین می‌تواند کلید API اضافه کند")
    settings.GAPGPT_API_KEY = req.api_key
    return {
        "id": 1,
        "provider": req.provider,
        "status": "connected",
    }

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import json
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..ai.gapgpt import get_ai_response, stream_ai_response, get_ai_config
from ..config import settings

router = APIRouter(prefix="/ai", tags=["ai"])


def _get_settings(db: Session) -> models.SystemSettings:
    """رکورد تنظیمات سیستم را برمی‌گرداند (اگر نبود می‌سازد)."""
    s = db.query(models.SystemSettings).first()
    if not s:
        s = models.SystemSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _active_api_key(db: Session) -> str:
    """کلید فعال: اول دیتابیس، بعد .env"""
    return get_ai_config(db)["api_key"]


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
    if not _active_api_key(db):
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
    response_text = await get_ai_response(messages, db=db)

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
    if not _active_api_key(db):
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
        async for chunk in stream_ai_response(messages, db=db):
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


@router.get("/trading-status")
async def get_ai_trading_status(
    current_user: models.User = Depends(get_current_user)
):
    return {"ai_trading_enabled": bool(current_user.ai_trading_enabled)}


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
    s = _get_settings(db)
    s.gapgpt_api_key = api_key
    db.commit()
    return {"message": "کلید API هوش مصنوعی ذخیره شد"}


@router.get("/connections")
async def get_ai_connections(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Returns AI provider connection status."""
    cfg = get_ai_config(db)
    return [
        {
            "id": 1,
            "provider": f"GapGPT ({cfg['model']})",
            "status": "connected" if cfg["api_key"] else "disconnected",
        }
    ]


class ConnectionRequest(BaseModel):
    provider: str
    api_key: str


@router.post("/connections")
async def add_ai_connection(
    req: ConnectionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save the GapGPT API key (persisted to database)."""
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین می‌تواند کلید API اضافه کند")
    s = _get_settings(db)
    s.gapgpt_api_key = req.api_key
    db.commit()
    return {
        "id": 1,
        "provider": req.provider,
        "status": "connected",
    }


@router.get("/models")
async def list_gapgpt_models(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """لیست واقعی مدل‌های در دسترس گپ‌جی‌پی‌تی را برمی‌گرداند."""
    cfg = get_ai_config(db)
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="ابتدا کلید API گپ‌جی‌پی‌تی را وارد کنید")

    from ..ai.gapgpt import make_client
    client = make_client(cfg["api_key"], timeout=30.0)
    try:
        resp = await client.models.list()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"اتصال به سرور گپ‌جی‌پی‌تی برقرار نشد: {type(e).__name__}",
        )

    model_ids = sorted({m.id for m in resp.data})
    return {"models": model_ids, "selected": cfg["model"]}


class ModelSelectRequest(BaseModel):
    model: str


@router.put("/model")
async def select_model(
    req: ModelSelectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """مدل انتخاب‌شده گپ‌جی‌پی‌تی را ذخیره می‌کند."""
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین می‌تواند مدل را تغییر دهد")
    s = _get_settings(db)
    s.gapgpt_model = req.model
    db.commit()
    return {"model": req.model}

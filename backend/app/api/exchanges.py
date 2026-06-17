from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..exchanges.nobitex import get_exchange, NobitexExchange

router = APIRouter(prefix="/exchanges", tags=["exchanges"])


class AddExchangeRequest(BaseModel):
    exchange_name: str
    api_key: str
    api_secret: Optional[str] = ""
    is_primary: bool = False


@router.get("/")
async def list_exchanges(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exchanges = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id
    ).all()
    return [{
        "id": e.id,
        "exchange_name": e.exchange_name,
        "api_key": e.api_key[:6] + "****" + e.api_key[-4:] if len(e.api_key) > 10 else "****",
        "is_primary": e.is_primary,
        "is_active": e.is_active,
        "balance": e.balance,
        "last_sync": e.last_sync,
        "created_at": e.created_at,
    } for e in exchanges]


@router.post("/")
async def add_exchange(
    req: AddExchangeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Test connection
    try:
        exch = get_exchange(req.exchange_name, req.api_key, req.api_secret)
        connected = await exch.test_connection()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        connected = False

    if not connected:
        raise HTTPException(status_code=400, detail="اتصال به صرافی ناموفق بود. کلید API را بررسی کنید")

    if req.is_primary:
        db.query(models.ExchangeAPI).filter(
            models.ExchangeAPI.user_id == current_user.id
        ).update({"is_primary": False})

    # Get initial balance
    balance = 0
    try:
        balances = await exch.get_balance()
        usdt = balances.get("USDT")
        if usdt:
            balance = usdt.total
    except Exception:
        pass

    new_exch = models.ExchangeAPI(
        user_id=current_user.id,
        exchange_name=req.exchange_name,
        api_key=req.api_key,
        api_secret=req.api_secret,
        is_primary=req.is_primary,
        balance=balance,
    )
    db.add(new_exch)
    db.commit()
    db.refresh(new_exch)
    return {"message": "صرافی با موفقیت اضافه شد", "id": new_exch.id}


@router.delete("/{exchange_id}")
async def remove_exchange(
    exchange_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exch = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.id == exchange_id,
        models.ExchangeAPI.user_id == current_user.id,
    ).first()
    if not exch:
        raise HTTPException(status_code=404, detail="صرافی یافت نشد")
    db.delete(exch)
    db.commit()
    return {"message": "صرافی حذف شد"}


@router.post("/{exchange_id}/sync")
async def sync_balance(
    exchange_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exch_record = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.id == exchange_id,
        models.ExchangeAPI.user_id == current_user.id,
    ).first()
    if not exch_record:
        raise HTTPException(status_code=404, detail="صرافی یافت نشد")
    try:
        exch = get_exchange(exch_record.exchange_name, exch_record.api_key, exch_record.api_secret)
        balances = await exch.get_balance()
        usdt = balances.get("USDT")
        if usdt:
            exch_record.balance = usdt.total
        from datetime import datetime
        exch_record.last_sync = datetime.utcnow()
        db.commit()
        return {"balance": exch_record.balance, "currencies": {k: v.total for k, v in balances.items()}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطا در دریافت موجودی: {str(e)}")

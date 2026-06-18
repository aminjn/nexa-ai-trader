from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..ml.trainer import get_trainer, FEATURE_NAMES

router = APIRouter(prefix="/model", tags=["model"])

# Training progress store (in-memory for simplicity)
_training_progress: dict = {"status": "idle", "progress": 0, "message": "", "accuracy": 0.0}


@router.get("/status")
async def get_model_status(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trainer = get_trainer()
    ml_model = db.query(models.MLModel).first()
    if not ml_model:
        ml_model = models.MLModel()
        db.add(ml_model)
        db.commit()
        db.refresh(ml_model)

    return {
        "status": _training_progress.get("status", ml_model.status),
        "accuracy": trainer.accuracy if trainer.is_trained else ml_model.accuracy,
        "is_trained": trainer.is_trained,
        "progress": _training_progress.get("progress", 0),
        "message": _training_progress.get("message", ""),
        "epochs_done": ml_model.epochs_done,
        "total_epochs": ml_model.total_epochs,
        "training_data_days": ml_model.training_data_days,
        "last_trained": ml_model.last_trained,
        "features": FEATURE_NAMES,
        "model_name": ml_model.name,
        "version": ml_model.version,
    }


async def _train_background():
    global _training_progress
    _training_progress = {"status": "training", "progress": 0, "message": "شروع آموزش..."}

    async def progress_cb(pct: int, msg: str):
        _training_progress["progress"] = pct
        _training_progress["message"] = msg

    from ..database import SessionLocal
    trainer = get_trainer()
    try:
        result = await trainer.train(progress_callback=progress_cb)
        _training_progress = {
            "status": "ready",
            "progress": 100,
            "message": "مدل آماده است",
            "accuracy": result["accuracy"],
        }
        db = SessionLocal()
        try:
            ml_model = db.query(models.MLModel).first()
            if ml_model:
                ml_model.status = "ready"
                ml_model.accuracy = result["accuracy"]
                ml_model.last_trained = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    except Exception as e:
        _training_progress = {"status": "error", "progress": 0, "message": f"خطا: {str(e)}"}


@router.post("/train")
async def start_training(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.is_superadmin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین می‌تواند مدل را آموزش دهد")

    if _training_progress.get("status") == "training":
        return {"message": "آموزش در حال انجام است"}

    background_tasks.add_task(_train_background)
    return {"message": "آموزش شروع شد"}


@router.get("/predict")
async def get_prediction(
    symbol: str = "BTC/USDT",
    current_user: models.User = Depends(get_current_user)
):
    trainer = get_trainer()
    if not trainer.is_trained:
        return {"signal": "WAIT", "confidence": 0, "message": "مدل هنوز آموزش ندیده است"}

    try:
        import httpx
        import pandas as pd
        from ..config import settings
        sym = symbol.replace("/", "")
        proxy = settings.GAPGPT_PROXY or None
        async with httpx.AsyncClient(timeout=10, proxy=proxy) as client:
            resp = await client.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": sym, "interval": "1h", "limit": 200}
            )
            data = resp.json()
        df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume",
                                          "ct","qv","tr","tbv","tbq","ign"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        result = trainer.predict(df)
        return result
    except Exception as e:
        return {"signal": "WAIT", "confidence": 0, "error": str(e)}

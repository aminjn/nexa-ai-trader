from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import asyncio
import io
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..ml.trainer import get_trainer, FEATURE_NAMES, accum_merge_save, accum_count
from ..trading.bot import log_bot_event

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
        "feature_importances": ml_model.feature_importances or [],
        "metrics": ml_model.metrics or {},
        "ai_explanation": ml_model.ai_explanation or "",
        "data_source": ml_model.data_source or "",
        "accumulated_rows": accum_count(),
        "model_name": ml_model.name,
        "version": ml_model.version,
        # آستانه‌ی تصمیم فعلی مدل (همیشه مقداری دارد، حتی اگر AI تنظیمش نکرده باشد)
        "confidence_threshold": round(trainer.confidence_threshold * 100, 1),
    }


@router.post("/upload-data")
async def upload_data(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
):
    """آپلود داده OHLCV (CSV) برای افزودن به مجموعه آموزش.

    ستون‌های لازم: timestamp, open, high, low, close, volume (symbol اختیاری)
    """
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین می‌تواند داده اضافه کند")
    import pandas as pd
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خواندن فایل ناموفق بود: {e}")
    try:
        merged = accum_merge_save(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_bot_event(f"📥 داده آموزشی اضافه شد ({len(df)} ردیف) — مجموع: {len(merged)}")
    return {"message": f"{len(df)} ردیف اضافه شد", "total": len(merged)}


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

        # ابتدا نتایج را ذخیره و وضعیت را «آماده» می‌کنیم تا پنل قفل نماند
        db = SessionLocal()
        try:
            ml_model = db.query(models.MLModel).first()
            if ml_model:
                ml_model.status = "ready"
                ml_model.accuracy = result["accuracy"]
                ml_model.feature_importances = result["feature_importances"]
                ml_model.metrics = result["metrics"]
                ml_model.data_source = result["source"]
                ml_model.last_trained = datetime.utcnow()
                db.commit()
        finally:
            db.close()

        _training_progress = {
            "status": "ready",
            "progress": 100,
            "message": "مدل آماده است",
            "accuracy": result["accuracy"],
        }
        log_bot_event(f"مدل آموزش دید — دقت {result['metrics'].get('accuracy')}٪ روی {result['metrics'].get('total_samples')} نمونه")

        # توضیح هوش مصنوعی (بهترین تلاش، با محدودیت زمانی — آموزش را بلوک نمی‌کند)
        try:
            ai_explanation = await asyncio.wait_for(_generate_ai_explanation(result), timeout=45)
            if ai_explanation:
                db2 = SessionLocal()
                try:
                    mm = db2.query(models.MLModel).first()
                    if mm:
                        mm.ai_explanation = ai_explanation
                        db2.commit()
                finally:
                    db2.close()
        except Exception:
            pass

        # ── هوش مصنوعی مدل را تنظیم می‌کند: آستانه تصمیم بهینه ──
        try:
            tuned = await asyncio.wait_for(_ai_tune_threshold(result), timeout=45)
            if tuned:
                trainer.set_threshold(tuned)
                db3 = SessionLocal()
                try:
                    mm = db3.query(models.MLModel).first()
                    if mm:
                        met = dict(mm.metrics or {})
                        met["ai_threshold"] = round(tuned * 100, 1)
                        mm.metrics = met
                        db3.commit()
                finally:
                    db3.close()
                log_bot_event(f"🧠 هوش مصنوعی مدل را تنظیم کرد — آستانه تصمیم: {round(tuned*100,1)}٪")
        except Exception:
            pass
    except Exception as e:
        _training_progress = {"status": "error", "progress": 0, "message": f"خطا: {str(e)}"}
        log_bot_event(f"خطا در آموزش مدل: {str(e)[:120]}")


async def _generate_ai_explanation(result: dict) -> str:
    """با کمک گپ‌جی‌پی‌تی توضیح می‌دهد مدل چه چیزی یاد گرفته است."""
    try:
        from ..ai.gapgpt import get_ai_response, get_ai_config
        from ..database import SessionLocal
        db = SessionLocal()
        try:
            if not get_ai_config(db)["api_key"]:
                return ""
            top = result["feature_importances"][:12]
            m = result["metrics"]
            lines = "\n".join([f"- {f['name']}: {f['importance']}٪" for f in top])
            prompt = (
                f"یک مدل یادگیری ماشین برای پیش‌بینی جهت قیمت رمزارز روی داده {m.get('source')} "
                f"({m.get('date_from')} تا {m.get('date_to')}، {m.get('total_samples')} نمونه) آموزش دید.\n"
                f"دقت: {m.get('accuracy')}٪ | Precision: {m.get('precision')}٪ | Recall: {m.get('recall')}٪\n\n"
                f"مهم‌ترین اندیکاتورهایی که مدل یاد گرفت (به ترتیب اهمیت):\n{lines}\n\n"
                "به‌صورت کوتاه و کاملاً فارسی توضیح بده: ۱) مدل عمدتاً روی چه نوع سیگنال‌هایی تکیه کرده "
                "۲) این یعنی چه استراتژی‌ای یاد گرفته ۳) محدودیت‌ها و ریسک‌ها. صادق باش و اغراق نکن."
            )
            return await get_ai_response([{"role": "user", "content": prompt}], db=db)
        finally:
            db.close()
    except Exception:
        return ""


async def _ai_tune_threshold(result: dict):
    """هوش مصنوعی بر اساس دقت/صحت مدل، آستانه تصمیم‌گیری بهینه را پیشنهاد می‌دهد."""
    try:
        import re
        from ..ai.gapgpt import get_ai_response, get_ai_config
        from ..database import SessionLocal
        db = SessionLocal()
        try:
            if not get_ai_config(db)["api_key"]:
                return None
            m = result["metrics"]
            prompt = (
                "تو یک مهندس یادگیری ماشین هستی. یک مدل طبقه‌بندی پیش‌بینی جهت قیمت رمزارز "
                f"با این مشخصات آموزش دید: دقت {m.get('accuracy')}٪، Precision {m.get('precision')}٪، "
                f"Recall {m.get('recall')}٪.\n"
                "ربات فقط وقتی معامله می‌کند که اطمینان مدل از یک «آستانه» بیشتر باشد. "
                "آستانه بالاتر = معاملات کمتر ولی مطمئن‌تر؛ آستانه پایین‌تر = معاملات بیشتر ولی پرریسک‌تر.\n"
                "با توجه به این آمار، یک آستانه‌ی بهینه بین 0.50 تا 0.70 پیشنهاد بده.\n"
                "فقط و فقط یک عدد اعشاری برگردان (مثلاً 0.56). هیچ توضیح اضافه‌ای نده."
            )
            resp = await get_ai_response([{"role": "user", "content": prompt}], db=db)
            match = re.search(r"0?\.\d+", resp or "")
            if match:
                val = float(match.group())
                if 0.5 <= val <= 0.75:
                    return val
            return None
        finally:
            db.close()
    except Exception:
        return None


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


async def auto_retrain_loop(interval_hours: float = 6.0):
    """هر چند ساعت یک‌بار مدل را با داده‌ی به‌روز دوباره آموزش می‌دهد."""
    while True:
        await asyncio.sleep(interval_hours * 3600)
        if _training_progress.get("status") != "training":
            log_bot_event("🔄 آموزش خودکار دوره‌ای مدل با داده جدید آغاز شد")
            await _train_background()


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

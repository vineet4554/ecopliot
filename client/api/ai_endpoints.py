import os
import json
import time
import pickle
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pandas as pd
import numpy as np

from ai.gemini_ai import GeminiAIService
from ocr.vision_svc import VisionAnalysisService
from ocr.ocr_svc import OCRService
from services.analysis_svc import BillAnalysisService

logger = logging.getLogger("ecopilot.ai_endpoints")
router = APIRouter(prefix="/ai", tags=["AI Endpoints"])

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "carbon_predictor.pkl"
)

def load_ml_model():
    """Loads the pickled machine learning pipeline model, training it if missing."""
    if not os.path.exists(MODEL_PATH):
        logger.warning(f"Predictor pickle not found at {MODEL_PATH}. Auto-training the model...")
        try:
            from ml.train import main as train_main
            train_main()
        except Exception as e:
            logger.error(f"Auto-training failed: {e}")

    if not os.path.exists(MODEL_PATH):
        return None

    try:
        with open(MODEL_PATH, "rb") as f:
            model_data = pickle.load(f)
            return model_data
    except Exception as e:
        logger.error(f"Error loading predictor pickle: {e}")
        return None

ML_MODEL_DATA = load_ml_model()


# --- REQUEST & RESPONSE SCHEMAS ---

class TwinSimRequest(BaseModel):
    toggles: Dict[str, bool]
    latest_logs: List[Dict[str, Any]]
    profile: Dict[str, Any]

class AssessRequest(BaseModel):
    travel: str
    food: str
    electricity: str
    waste: str
    water: str

class SummarizeRequest(BaseModel):
    chat_history: List[Dict[str, Any]]

class StreamChatRequest(BaseModel):
    chat_history: List[Dict[str, Any]]
    new_message: str
    history_summary: Optional[str] = None

class ReportSummarizeRequest(BaseModel):
    report_type: str
    trend: Dict[str, Any]
    predictions: List[Dict[str, Any]]
    achievements: Dict[str, Any]


# --- ENDPOINTS ---

@router.post("/twin/simulate")
async def simulate_twin(payload: TwinSimRequest):
    global ML_MODEL_DATA
    if ML_MODEL_DATA is None:
        ML_MODEL_DATA = load_ml_model()

    profile = {
        'Body Type': 'normal',
        'Sex': 'female',
        'Diet': payload.profile.get('diet_preference', 'omnivore'),
        'How Often Shower': 'daily',
        'Heating Energy Source': 'electricity',
        'Transport': 'private',
        'Vehicle Type': 'petrol',
        'Social Activity': 'sometimes',
        'Monthly Grocery Bill': 150,
        'Frequency of Traveling by Air': 'rarely',
        'Vehicle Monthly Distance Km': 500,
        'Waste Bag Size': 'medium',
        'Waste Bag Weekly Count': 2,
        'How Long TV PC Daily Hour': 4,
        'How Many New Clothes Monthly': 2,
        'How Long Internet Daily Hour': 3,
        'Energy efficiency': 'Sometimes',
        'Recycling': "['Paper', 'Plastic']",
        'Cooking_With': "['Stove', 'Oven']"
    }

    # Enrich from logs
    if payload.latest_logs:
        latest_log = payload.latest_logs[0]
        categories = latest_log.get("categories", {})
        
        if "transport" in categories:
            t_data = categories["transport"]
            profile['Vehicle Type'] = t_data.get("mode", "petrol")
            profile['Vehicle Monthly Distance Km'] = int(t_data.get("distance_km", 500))
            profile['Transport'] = 'private' if t_data.get("mode") in ["petrol", "diesel", "hybrid", "electric"] else 'public'
            
        if "food" in categories:
            profile['Diet'] = categories["food"].get("diet_type", "omnivore")
            
        if "waste" in categories:
            w_data = categories["waste"]
            if w_data.get("recycled"):
                profile['Recycling'] = "['Paper', 'Plastic', 'Glass', 'Metal']"
            else:
                profile['Recycling'] = "[]"

    # Baseline prediction
    baseline_co2 = 500.0
    if ML_MODEL_DATA:
        try:
            df_base = pd.DataFrame([profile])
            baseline_co2 = float(ML_MODEL_DATA['pipeline'].predict(df_base)[0])
        except Exception as e:
            logger.error(f"ML baseline prediction failed: {e}")
            baseline_co2 = 500.0

    # Apply toggles
    sim_profile = profile.copy()
    toggles = payload.toggles
    if toggles.get('buy_ev'):
        sim_profile['Vehicle Type'] = 'electric'
        sim_profile['Transport'] = 'private'
    if toggles.get('install_solar'):
        sim_profile['Heating Energy Source'] = 'electricity'
        sim_profile['Energy efficiency'] = 'Yes'
    if toggles.get('stop_flying'):
        sim_profile['Frequency of Traveling by Air'] = 'never'
    if toggles.get('reduce_ac'):
        sim_profile['How Long TV PC Daily Hour'] = max(1, sim_profile['How Long TV PC Daily Hour'] - 2)

    projected_co2 = baseline_co2
    if ML_MODEL_DATA:
        try:
            df_sim = pd.DataFrame([sim_profile])
            projected_co2 = float(ML_MODEL_DATA['pipeline'].predict(df_sim)[0])
        except Exception as e:
            logger.error(f"ML simulated prediction failed: {e}")
            projected_co2 = baseline_co2
            if toggles.get('buy_ev'): projected_co2 -= 120.0
            if toggles.get('install_solar'): projected_co2 -= 80.0
            if toggles.get('stop_flying'): projected_co2 -= 100.0
            if toggles.get('reduce_ac'): projected_co2 -= 30.0
    else:
        if toggles.get('buy_ev'): projected_co2 -= 120.0
        if toggles.get('install_solar'): projected_co2 -= 80.0
        if toggles.get('stop_flying'): projected_co2 -= 100.0
        if toggles.get('reduce_ac'): projected_co2 -= 30.0

    projected_co2 = max(50.0, projected_co2)
    reduction_kg = max(0.0, baseline_co2 - projected_co2)
    reduction_pct = (reduction_kg / baseline_co2) * 100 if baseline_co2 > 0 else 0.0

    # Gemini analysis
    gemini_svc = GeminiAIService()
    try:
        gemini_result = await gemini_svc.analyze_twin_simulation(
            original_co2=baseline_co2,
            projected_co2=projected_co2,
            buy_ev=toggles.get('buy_ev', False),
            install_solar=toggles.get('install_solar', False),
            stop_flying=toggles.get('stop_flying', False),
            reduce_ac=toggles.get('reduce_ac', False)
        )
    except Exception as e:
        logger.error(f"Gemini twin simulation analysis failed: {e}")
        gemini_result = {
            "savings_usd_desc": "$50 - $120 / month saved on resources",
            "lifestyle_impact": "Adopting these eco-friendly adjustments drives down your carbon score significantly.",
            "top_savings_sources": ["Simulated lifestyle improvements"]
        }

    # Seasonal chart calculations
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    current_month_idx = datetime.now().month - 1
    
    chart_data = []
    for i in range(6):
        m_idx = (current_month_idx + i) % 12
        m_name = months[m_idx]
        
        if m_idx in [5, 6, 7]:  # Jun, Jul, Aug
            season_factor = 1.18
            sim_season_factor = 1.03 if (toggles.get('install_solar') or toggles.get('reduce_ac')) else 1.18
        elif m_idx in [11, 0, 1]:  # Dec, Jan, Feb
            season_factor = 1.10
            sim_season_factor = 1.05 if toggles.get('install_solar') else 1.10
        else:
            season_factor = 1.0
            sim_season_factor = 1.0
            
        m_current = round(baseline_co2 * season_factor, 1)
        m_simulated = round(projected_co2 * sim_season_factor, 1)
        
        chart_data.append({
            "month": m_name,
            "current": m_current,
            "simulated": m_simulated
        })

    return {
        "original_co2_kg": round(baseline_co2, 2),
        "projected_co2_kg": round(projected_co2, 2),
        "reduction_kg": round(reduction_kg, 2),
        "reduction_pct": round(reduction_pct, 2),
        "savings_usd_desc": gemini_result.get("savings_usd_desc", ""),
        "lifestyle_impact": gemini_result.get("lifestyle_impact", ""),
        "top_savings_sources": gemini_result.get("top_savings_sources", []),
        "chart_data": chart_data
    }


@router.post("/ocr/bill")
async def ocr_bill(file: UploadFile = File(...)):
    file_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"
    filename = file.filename or "statement.jpg"

    gemini = GeminiAIService()
    analysis_service = BillAnalysisService(gemini)
    
    parsed_data = None
    ocr_text = ""
    
    # Try direct multimodal first
    if not gemini.is_mock:
        try:
            parsed_data = await analysis_service.analyze_bill_multimodal(file_bytes, content_type)
            ocr_text = (
                f"Multimodal Scan Results:\n"
                f"Period: {parsed_data.get('billing_period')}\n"
                f"Consumption: {parsed_data.get('consumption_value')} {parsed_data.get('consumption_unit')}\n"
                f"Cost: {parsed_data.get('total_cost')}"
            )
        except Exception as e:
            logger.warning(f"Direct multimodal analysis failed: {e}. Falling back to OCR pipeline...")

    # Fallback to OCR + Text analysis
    if not parsed_data:
        ocr_service = OCRService()
        ocr_text = await ocr_service.perform_ocr(file_bytes, filename, content_type)
        if not ocr_text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to extract readable text from statement. Ensure the document is clear."
            )
        try:
            parsed_data = await analysis_service.analyze_bill_text(ocr_text)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process utility statement: {e}"
            )
            
    return {
        "billing_period": parsed_data.get("billing_period"),
        "consumption_value": parsed_data.get("consumption_value"),
        "consumption_unit": parsed_data.get("consumption_unit"),
        "total_cost": parsed_data.get("total_cost"),
        "savings_opportunities": parsed_data.get("savings_opportunities", []),
        "extracted_raw_text": ocr_text
    }


@router.post("/ocr/room")
async def ocr_room(file: UploadFile = File(...), room_type: str = Form("living_room")):
    file_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"

    gemini = GeminiAIService()
    vision_svc = VisionAnalysisService(gemini)

    try:
        audit_data = await vision_svc.audit_room_image(file_bytes, content_type, room_type)
        return audit_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan room image: {e}"
        )


@router.post("/coach/assess")
async def coach_assess(payload: AssessRequest):
    gemini = GeminiAIService()
    try:
        assessment_json = await gemini.analyze_sustainability(
            travel=payload.travel,
            food=payload.food,
            electricity=payload.electricity,
            waste=payload.waste,
            water=payload.water
        )
        return assessment_json
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gemini habits analysis failed: {e}"
        )


@router.post("/coach/summarize")
async def coach_summarize(payload: SummarizeRequest):
    gemini = GeminiAIService()
    try:
        summary = await gemini.generate_history_summary(payload.chat_history)
        return {"summary": summary}
    except Exception as e:
        logger.error(f"Error computing history summary: {e}")
        return {"summary": "The user and EcoPilot previously discussed sustainability habits."}


@router.post("/coach/chat/stream")
async def coach_chat_stream(payload: StreamChatRequest):
    gemini = GeminiAIService()
    async def event_generator():
        try:
            async for chunk in gemini.generate_chat_response_stream(
                payload.chat_history, payload.new_message, history_summary=payload.history_summary
            ):
                if chunk:
                    yield chunk
        except Exception as e:
            logger.error(f"Streaming generator encountered error: {e}")
            yield "\n\n[Coach Connection Error. Swapping commute modes or swap bulbs parameters to reduce draws.]"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/report/summarize")
async def report_summarize(payload: ReportSummarizeRequest):
    gemini = GeminiAIService()
    try:
        summary = await gemini.generate_report_summary(
            report_type=payload.report_type,
            trend=payload.trend,
            predictions=payload.predictions,
            achievements=payload.achievements
        )
        return {"summary": summary}
    except Exception as e:
        logger.error(f"Failed to generate AI report summary: {e}")
        direction = payload.trend.get("direction", "stable")
        current_co2 = payload.trend.get("total_co2_kg", 0.0)
        ai_summary = (
            f"EcoPilot report review: Carbon footprint was {current_co2:.2f} kg CO2e, showing a "
            f"{payload.trend.get('percentage_change', 0.0):.1f}% {direction} versus prior period. "
            "Keep working on optimizing utility drawer draws and swapping transport options!"
        )
        return {"summary": ai_summary}

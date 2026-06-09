import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.settings import EnvironmentType
from api import ai_endpoints
from middleware.security_headers import SecurityHeadersMiddleware

# Configure logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="EcoPilot AI - Stateless AI Microservice",
    description="Stateless AI/ML/OCR microservice for the EcoPilot AI sustainability platform.",
    version="1.0.0"
)

# Register Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    if settings.environment == EnvironmentType.PRODUCTION:
        detail = "Internal Server Error"
    else:
        detail = f"Internal Server Error: {str(exc)}"
    return JSONResponse(
        status_code=500,
        content={
            "detail": detail,
            "type": type(exc).__name__
        }
    )

# Register routes
app.include_router(ai_endpoints.router)

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "EcoPilot AI Stateless Client Microservice",
        "environment": settings.environment
    }

@app.get("/health")
async def health_check():
    from ai.gemini_ai import GeminiAIService
    gemini = GeminiAIService()
    ai_status = "mock-offline" if gemini.is_mock else "healthy"
    
    return {
        "status": "healthy",
        "ai_service": ai_status,
        "environment": settings.environment
    }

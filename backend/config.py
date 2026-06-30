from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_LIVE_MODEL: str = "gemini-2.5-flash-live-preview"
    MAX_UPLOAD_MB: int = 100
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Optional but recommended for evidence-grade multi-source checks.
    # Google CSE: targeted searches across trusted domains like TOI/BBC/NDTV/etc.
    GOOGLE_CSE_API_KEY: str | None = None
    GOOGLE_CSE_ID: str | None = None

    # Google Fact Check Tools API key for ClaimReview lookup.
    FACT_CHECK_API_KEY: str | None = None

    # Optional article discovery provider. GDELT + RSS work without this.
    NEWSAPI_KEY: str | None = None

    # Local folder where auditable JSON evidence bundles are stored.
    EVIDENCE_DIR: str = "evidence_reports"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

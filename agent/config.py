"""Application settings loaded from environment.

All config is centralized here so the rest of the codebase
imports `settings` and never reads os.environ directly.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMMA_LOCAL = "gemma_local"
    GEMMA_VERTEX = "gemma_vertex"


class STTProvider(str, Enum):
    IVRIT_AI = "ivrit_ai"
    OPENAI_WHISPER = "openai_whisper"
    AZURE = "azure"


class TTSProvider(str, Enum):
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    GOOGLE = "google"


class EmbeddingProvider(str, Enum):
    COHERE = "cohere"
    OPENAI = "openai"
    VOYAGE = "voyage"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LiveKit
    livekit_url: str = "wss://localhost:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # LLM
    llm_provider: LLMProvider = LLMProvider.ANTHROPIC
    llm_model: str = "claude-sonnet-4-7"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_application_credentials: str = ""
    vertex_project_id: str = ""
    vertex_region: str = "me-west1"  # Tel Aviv
    gemma_local_url: str = "http://localhost:8001/v1"
    gemma_local_model: str = "gemma-4-31b-it"

    # STT
    stt_provider: STTProvider = STTProvider.IVRIT_AI
    ivrit_ai_model: str = "ivrit-ai/whisper-large-v3-turbo"
    azure_speech_key: str = ""
    azure_speech_region: str = "israelcentral"

    # TTS
    tts_provider: TTSProvider = TTSProvider.ELEVENLABS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"

    # Embeddings
    embedding_provider: EmbeddingProvider = EmbeddingProvider.COHERE
    cohere_api_key: str = ""
    embedding_model: str = "embed-multilingual-v3.0"

    # Vector DB
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "ptsd_articles_he"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    livekit_sip_trunk_id: str = ""

    # Safety
    crisis_hotline_eran: str = "1201"
    crisis_hotline_natal: str = "1-800-363-363"
    enable_crisis_detection: bool = True

    # Observability
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    sentry_dsn: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 7880
    environment: Literal["development", "staging", "production"] = "development"

    # RAG tuning
    rag_top_k: int = Field(default=4, description="Number of chunks to retrieve")
    rag_score_threshold: float = Field(default=0.6, description="Min similarity score")
    rag_max_context_tokens: int = Field(default=2000, description="Max context tokens")


settings = Settings()

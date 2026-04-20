"""LiveKit voice agent for PTSD-Ai.

Wires together: VAD → STT → Safety → RAG → LLM → TTS, with streaming
interruption handling. Designed for phone-call-like UX with no buttons.

Run:
    python -m agent.main dev   # local development
    python -m agent.main start # production
"""

from __future__ import annotations

import logging
from typing import AsyncIterable

from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm as lk_llm,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import silero

from agent.config import settings, LLMProvider, STTProvider, TTSProvider
from agent.prompts import build_system_prompt, GREETINGS_HE
from agent.rag import get_rag
from agent.safety import (
    assess_user_input,
    filter_agent_output,
    RiskLevel,
)

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("ptsd-ai.agent")


# =============================================================================
# Provider builders - swap between Claude/GPT/Gemma without touching anything else
# =============================================================================

def build_llm() -> lk_llm.LLM:
    if settings.llm_provider == LLMProvider.ANTHROPIC:
        from livekit.plugins import anthropic
        return anthropic.LLM(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            temperature=0.7,
        )
    if settings.llm_provider == LLMProvider.OPENAI:
        from livekit.plugins import openai
        return openai.LLM(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            temperature=0.7,
        )
    if settings.llm_provider == LLMProvider.GEMMA_LOCAL:
        # Gemma 4 served via vLLM with OpenAI-compatible API
        from livekit.plugins import openai
        return openai.LLM.with_ollama(
            model=settings.gemma_local_model,
            base_url=settings.gemma_local_url,
            temperature=0.7,
        )
    if settings.llm_provider == LLMProvider.GEMMA_VERTEX:
        from livekit.plugins import google
        return google.LLM(
            model="gemma-4-31b-it",
            project=settings.vertex_project_id,
            location=settings.vertex_region,
            temperature=0.7,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def build_stt():
    if settings.stt_provider == STTProvider.IVRIT_AI:
        # Local Whisper fine-tuned on Hebrew. Best Hebrew quality.
        from livekit.plugins import openai
        # ivrit-ai whisper served via faster-whisper-server (OpenAI-compatible)
        return openai.STT.with_groq(  # placeholder - replace with local server
            model=settings.ivrit_ai_model,
            language="he",
        )
    if settings.stt_provider == STTProvider.OPENAI_WHISPER:
        from livekit.plugins import openai
        return openai.STT(
            api_key=settings.openai_api_key,
            language="he",
            model="whisper-1",
        )
    if settings.stt_provider == STTProvider.AZURE:
        from livekit.plugins import azure
        return azure.STT(
            speech_key=settings.azure_speech_key,
            speech_region=settings.azure_speech_region,
            language="he-IL",
        )
    raise ValueError(f"Unknown STT provider: {settings.stt_provider}")


def build_tts():
    if settings.tts_provider == TTSProvider.ELEVENLABS:
        from livekit.plugins import elevenlabs
        return elevenlabs.TTS(
            api_key=settings.elevenlabs_api_key,
            voice=elevenlabs.Voice(
                id=settings.elevenlabs_voice_id,
                name="Hebrew Voice",
                category="premade",
            ),
            model=settings.elevenlabs_model,
            language="he",
        )
    if settings.tts_provider == TTSProvider.AZURE:
        from livekit.plugins import azure
        return azure.TTS(
            speech_key=settings.azure_speech_key,
            speech_region=settings.azure_speech_region,
            voice="he-IL-AvriNeural",  # or HilaNeural
            language="he-IL",
        )
    if settings.tts_provider == TTSProvider.GOOGLE:
        from livekit.plugins import google
        return google.TTS(
            language="he-IL",
            voice_name="he-IL-Wavenet-A",
        )
    raise ValueError(f"Unknown TTS provider: {settings.tts_provider}")


# =============================================================================
# Hooks: inject RAG context + safety pre/post-processing
# =============================================================================

async def before_llm_cb(
    agent: VoicePipelineAgent,
    chat_ctx: lk_llm.ChatContext,
) -> None:
    """Called right before the LLM is invoked.

    1. Run safety assessment on the latest user message.
    2. If crisis -> short-circuit with crisis response.
    3. Otherwise -> retrieve RAG chunks and inject as context.
    """
    user_msg = _last_user_text(chat_ctx)
    if not user_msg:
        return

    # --- Safety check ---
    assessment = assess_user_input(user_msg)
    logger.info("Safety: risk=%s phrases=%s", assessment.risk, assessment.triggered_phrases)

    if assessment.risk == RiskLevel.CRISIS and assessment.suggested_response:
        # Replace the conversation with a direct crisis response
        # by appending it as a "system" instruction at the end.
        chat_ctx.append(
            role="system",
            text=(
                "המשתמש במצוקה אקוטית. עכשיו, אמור לו במילים שלך משהו "
                "שמשקף את התוכן הבא, בחום, בקצב איטי, בלי למהר:\n"
                f"{assessment.suggested_response}"
            ),
        )
        return

    # --- RAG retrieval ---
    try:
        rag = get_rag()
        chunks = await rag.retrieve(user_msg)
        if chunks:
            context = rag.format_context(chunks, max_tokens=settings.rag_max_context_tokens)
            chat_ctx.append(
                role="system",
                text=(
                    "מידע רלוונטי ממאגר המאמרים (לרקע פנימי - אל תצטט):\n"
                    + context
                ),
            )
            logger.info("RAG: injected %d chunks", len(chunks))
    except Exception as e:
        logger.exception("RAG retrieval failed (continuing without): %s", e)


def _last_user_text(chat_ctx: lk_llm.ChatContext) -> str:
    for msg in reversed(chat_ctx.messages):
        if msg.role == "user":
            return msg.content if isinstance(msg.content, str) else ""
    return ""


# =============================================================================
# Entrypoint
# =============================================================================

async def entrypoint(ctx: JobContext) -> None:
    logger.info("Connecting to room %s", ctx.room.name)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info("Participant joined: %s", participant.identity)

    # Build pipeline components
    initial_ctx = lk_llm.ChatContext().append(
        role="system",
        text=build_system_prompt(),
    )

    agent = VoicePipelineAgent(
        vad=silero.VAD.load(
            min_silence_duration=0.4,  # natural pause before responding
            activation_threshold=0.5,
        ),
        stt=build_stt(),
        llm=build_llm(),
        tts=build_tts(),
        chat_ctx=initial_ctx,
        before_llm_cb=before_llm_cb,
        # Allow user to interrupt the agent mid-sentence (natural conversation)
        allow_interruptions=True,
        interrupt_speech_duration=0.5,
        interrupt_min_words=2,
    )

    agent.start(ctx.room, participant)

    # Greet the user
    import random
    greeting = random.choice(GREETINGS_HE)
    await agent.say(greeting, allow_interruptions=True)

    # Keep the session alive; LiveKit handles disconnect cleanup
    logger.info("Agent ready, conversation in progress...")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )

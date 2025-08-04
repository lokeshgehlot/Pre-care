import logging
from dotenv import load_dotenv

from livekit.agents import (
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    RoomOutputOptions,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.plugins import silero, deepgram
from livekit.plugins.google.llm import LLM as GeminiLLM
from livekit.plugins.azure import TTS as AzureTTS
from livekit.agents.voice import MetricsCollectedEvent

from precare_agent.agent import PreCareAgent

logger = logging.getLogger("main")
load_dotenv()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.05,
        min_silence_duration=0.3,
        prefix_padding_duration=0.2,
        activation_threshold=0.5
    )

    stt = deepgram.STT(model="nova-3", language="multi")
    proc.userdata["stt"] = stt

    # Prewarm Deepgram STT with silent audio
    import numpy as np
    import soundfile as sf
    import io
    silent_audio = np.zeros(int(0.2 * 16000), dtype=np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, silent_audio, 16000, format='WAV')
    buffer.seek(0)
    stt.recognize(buffer.read())

    proc.userdata["llm"] = GeminiLLM(
        model="models/gemini-1.5-flash",
        temperature=0.6,
    )

    proc.userdata["tts"] = AzureTTS()  # ✅ Plain text input (no SSML)

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        llm=ctx.proc.userdata["llm"],
        stt=ctx.proc.userdata["stt"],
        tts=ctx.proc.userdata["tts"],
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=PreCareAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))

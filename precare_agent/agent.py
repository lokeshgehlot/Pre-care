import logging
import time
import re

from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from langdetect import detect

logger = logging.getLogger("precare-agent")

def clean_text_for_tts(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\s.,:;<>/\-\n\r]", "", text)

def split_text(text: str):
    return re.split(r'(?<=[.?!।])\s+', text)

def detect_language(text: str) -> str:
    try:
        lang = detect(text)
        return "hi" if lang == "hi" else "en"
    except:
        return "en"

class PreCareAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are HeyDoc, a kind and friendly virtual healthcare assistant.
            Speak naturally.

            ❌ Do NOT give emergency advice.
            ❌ Do NOT diagnose.
            ✅ Just guide and talk naturally.
            """
        )
        self.last_start_time = None

    async def on_enter(self):
        self.session.generate_reply()

    async def on_input_start(self):
        self.last_start_time = time.time()
        await self.session.audio.stop_playback()

    async def on_transcript(self, transcript):
        if transcript.is_final:
            logger.info(f"📝 Final transcript: {transcript.text}")
            try:
                if await self.is_user_done(transcript.text):
                    await self.speak_in_chunks("Okay, take care! Disconnecting now.")
                    await self.session.disconnect()
                    return
            except Exception as e:
                logger.warning(f"Gemini goodbye check failed: {e}")

            await self.session.generate_reply(transcript.text)
        else:
            logger.debug(f"🔄 Interim transcript: {transcript.text}")

    async def is_user_done(self, text: str) -> bool:
            prompt = f"""
            The user said: "{text}"

            Is this message an attempt to politely end the conversation?
            Reply only with 'yes' or 'no'.
            """
            result = await self.session.llm.prompt(prompt)
            decision = result.text.strip().lower()
            logger.info(f"🤖 Gemini goodbye check: {decision}")
            return decision.startswith("yes")

    def format_response(self, text: str) -> str:
        if self.last_start_time:
            elapsed = time.time() - self.last_start_time
            logger.info(f"⏱️ Response time: {elapsed:.2f} seconds")
            self.last_start_time = None

        clean = clean_text_for_tts(text)

        # Use only hi-IN-AartiNeural
        voice = "hi-IN-AartiNeural"
        language = "hi-IN"

        # Set TTS config for session
        self.session.set_tts_config(
            language=language,
            voice_name=voice,
            use_streaming=True,
            enable_ssml=False  # ✅ Avoid SSML for faster response and fewer errors
        )

        return clean

    async def speak_in_chunks(self, full_text: str):
        chunks = split_text(full_text)
        for chunk in chunks:
            if not chunk.strip():
                continue
            text = self.format_response(chunk)
            await self.session.speak(text)

    @function_tool
    async def check_symptom(self, context: RunContext, symptom: str):
        return (
            f"{symptom} ke liye kuch common reasons ho sakte hain jaise mild infection ya allergy. "
            f"Thoda rest kariye aur pani zyada piye. Agar problem continue ho, toh ek doctor se consult zaroor kariye."
        )

    @function_tool
    async def lookup_medication(self, context: RunContext, name: str):
        return (
            f"{name} commonly pain ya fever ke liye use hoti hai. "
            f"Hamesha dosage instructions follow kariye ya professional advice lijiye before use."
        )

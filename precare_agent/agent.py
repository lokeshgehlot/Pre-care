import logging
import time
import re

from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from precare_agent.utils import detect_language

logger = logging.getLogger("precare-agent")

def clean_text_for_tts(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\s.,:;<>/\-\n\r]", "", text)

def split_text(text: str):
    return re.split(r'(?<=[.?!।])\s+', text)

class PreCareAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are HeyDoc, a kind and friendly virtual healthcare assistant.
            Speak in SSML format to control tone, pauses, and natural rhythm.

            ALWAYS wrap your responses in <speak>...</speak> tags, and use <break time='300ms'/> for pauses.

            Mix Hindi and English — like an Indian speaking over the phone.

            🎯 Style Guide:
            - Hindi for comfort and empathy.
            - English for medical or technical terms.
            - Short, helpful, friendly phrases.
            - Sounds like a real voice call.

            📞 Example:
            <speak>Namaste! Main HeyDoc hoon. <break time='300ms'/> Aapka health assistant. Aaj kaise madad kar sakta hoon?</speak>

            If unsure:
            <speak>Main uska exact answer nahi de sakta, <break time='150ms'/> lekin main aapki help karne ki poori koshish karoonga.</speak>

            ❌ Do NOT give emergency advice.
            ❌ Do NOT diagnose.
            ✅ Just guide and talk naturally.

            ❌ Avoid special characters like *, #, @, $, %, ^, &, etc. in your responses.
            """
        )
        self.last_start_time = None

    async def on_enter(self):
        self.session.generate_reply()

    async def on_input_start(self):
        self.last_start_time = time.time()
        await self.session.audio.stop_playback()  # Interrupt TTS playback on new input

    async def on_transcript(self, transcript):
        if transcript.is_final:
            logger.info(f"📝 Final transcript: {transcript.text}")

            # ✅ Ask Gemini if user wants to end the conversation
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
            logger.info(f"⏱️ Time taken for response: {elapsed:.2f} seconds")
            self.last_start_time = None

        clean_text = clean_text_for_tts(text)

        if not clean_text.strip().startswith("<speak>"):
            clean_text = f"<speak>{clean_text}</speak>"

        lang = detect_language(clean_text)
        logger.info(f"🌐 Detected language: {lang}")

        # Dynamically switch voice based on language
        if lang == "en":
            self.session.set_tts_config(
                language="en-IN",
                voice_name="en-IN-Wavenet-D",
                use_streaming=False,
                enable_ssml=True,
            )
        else:
            self.session.set_tts_config(
                language="hi-IN",
                voice_name="hi-IN-Wavenet-A",
                use_streaming=False,
                enable_ssml=True,
            )

        return clean_text

    async def speak_in_chunks(self, full_text: str):
        chunks = split_text(full_text)
        for chunk in chunks:
            if not chunk.strip():
                continue
            ssml = self.format_response(chunk)
            await self.session.speak(ssml)

    @function_tool
    async def check_symptom(self, context: RunContext, symptom: str):
        logger.info(f"Checking symptom: {symptom}")
        return (
            f"<speak>{symptom} ke liye kuch common reasons ho sakte hain jaise mild infection ya allergy. "
            f"<break time='300ms'/> Aap rest kariye aur pani zyada piye. Agar problem continue ho, toh ek doctor se consult zaroor kariye.</speak>"
        )

    @function_tool
    async def lookup_medication(self, context: RunContext, name: str):
        logger.info(f"Looking up medication: {name}")
        return (
            f"<speak>{name} commonly pain ya fever ke liye use hoti hai. "
            f"<break time='300ms'/> Hamesha dosage instructions follow kariye ya professional advice lijiye before use.</speak>"
        )

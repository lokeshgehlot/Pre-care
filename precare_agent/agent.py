import logging
import time
import re

from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from precare_agent.utils import detect_language  

logger = logging.getLogger("precare-agent")


def clean_text_for_tts(text: str) -> str:
    # Remove unwanted special characters except valid SSML tags and punctuation
    # Allow <, >, / for SSML tags; allow punctuation like . , : ; and space and alphanumerics
    # This regex removes characters like *, #, @, $, %, ^, &, etc.
    return re.sub(r"[^a-zA-Z0-9\s.,:;<>/\-\n\r]", "", text)


class PreCareAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are devin, a kind and friendly virtual healthcare assistant.
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

    def format_response(self, text: str) -> str:
        # Measure latency
        if self.last_start_time:
            elapsed = time.time() - self.last_start_time
            logger.info(f"⏱️ Time taken for response: {elapsed:.2f} seconds")
            self.last_start_time = None

        # Clean text to avoid special characters being read literally
        clean_text = clean_text_for_tts(text)

        # Ensure response is wrapped in <speak>...</speak>
        if not clean_text.strip().startswith("<speak>"):
            clean_text = f"<speak>{clean_text}</speak>"

        # Detect response language
        lang = detect_language(clean_text)
        logger.info(f"🌐 Detected language: {lang}")

        # Dynamically switch TTS voice
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

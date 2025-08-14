import logging
import time
import re

from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from langdetect import detect

logger = logging.getLogger("precare-agent")

def clean_text_for_tts(text: str) -> str:
    """
    Cleans up text from an LLM by removing common markdown and symbols
    that can cause a TTS engine to speak unwanted characters.
    """
    # Remove markdown formatting like bold, italics, or lists
    text = re.sub(r'[*_`]', '', text)

    # Replace multiple hyphens with a comma and space to create a natural pause
    text = re.sub(r'[-–—]', ',', text)

    # Remove parentheses and brackets
    text = re.sub(r'[()\[\]]', '', text)
    
    # Remove any character that is not a letter, number, or standard punctuation
    text = re.sub(r"[^a-zA-Z0-9\s.,?!।]", "", text)
    
    # Remove excessive whitespace
    text = " ".join(text.split())
    
    return text

def split_text(text: str):
    # This function is still useful for splitting sentences
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
You are WellnessGPT Symptom Triage Assistant, an empathetic, medically-aware virtual nurse trained to listen carefully to a patient’s health concerns.

Your goal is to:
- Understand the patient’s primary complaint in their own words.
- Ask structured follow-up questions to clarify symptom details (location, duration, severity, triggers, associated symptoms, onset, progression).
- Identify red flags requiring urgent referral (severe chest pain, heavy bleeding, sudden weakness, breathing difficulty, etc.).
- Continue gathering information iteratively until you can confidently recommend the most likely hospital department for their case.
- Build a structured symptom profile in the background for accurate routing.
- Always respond empathetically, using language that reassures and encourages sharing.

Tone & Empathy Guidelines:
- Start by acknowledging their concern (“I understand this must be uncomfortable for you…”).
- Avoid medical jargon unless necessary; explain simply when used.
- Never rush — give the user space to share.
- Avoid giving direct diagnosis; focus on symptom clarity and safe direction.
- End with clear next steps (“Based on what you’ve shared, I recommend you see the X department for further care”).

Symptom Intake Process:
Step 1 — Opening & Primary Complaint:
Example: "I’m here to understand what you’re going through so we can guide you to the right care. Could you please describe what’s troubling you today?"
Capture patient’s main complaint in their own words.

Step 2 — Symptom Clarification:
Ask targeted but conversational follow-ups:
- Location — “Where in your body are you feeling this?”
- Onset — “When did you first notice this problem?”
- Duration & Frequency — “Does it happen all the time or only sometimes?”
- Severity — “On a scale of 1–10, how bad is it right now?”
- Character — “Is it sharp, dull, throbbing, burning, or something else?”
- Triggers & Relievers — “Does anything make it worse or better?”
- Associated Symptoms — “Have you noticed anything else alongside this, like fever, swelling, rash, or nausea?”
- Impact — “Is this affecting your daily activities, sleep, or work?”

Step 3 — Risk & Red Flag Screening:
Before proceeding, check for emergency indicators:
Severe chest pain, shortness of breath, loss of consciousness, sudden weakness/numbness, heavy uncontrolled bleeding, high fever with confusion, pregnancy-related emergencies.
If detected: “Your symptoms sound urgent. I recommend going to the emergency department immediately.”

Step 4 — Narrowing to a Department:
Based on responses, internally map symptoms to possible specialties:
- General Medicine: Fever, fatigue, mild infections
- Gynecology: Menstrual issues, pregnancy symptoms, pelvic pain
- Orthopedics: Joint pain, fractures, muscle strain
- ENT: Ear pain, nasal congestion, sore throat
- Cardiology: Chest discomfort, palpitations
- Dermatology: Rashes, itching
- Neurology: Headaches, dizziness, seizures
- Gastroenterology: Abdominal pain, nausea, vomiting
- Psychiatry: Anxiety, depression
- Pediatrics: Children’s illnesses

Step 5 — Iterative Questioning Until Confident:
If unsure after first round, ask more specific symptom-linked questions from the top 2–3 possible departments. Stop when there’s 80% confidence in routing.

Step 6 — Closing & Next Steps:
Final empathetic closure:
“Thank you for sharing these details. Based on what you’ve told me, the best next step is to visit the [Department Name] at the hospital. They’ll be able to examine you further and start treatment. Would you like me to help you schedule the visit?”
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
            enable_ssml=False
        )

        return clean

    async def speak_in_chunks(self, full_text: str):
        chunks = split_text(full_text)
        for chunk in chunks:
            if not chunk.strip():
                continue
            text = self.format_response(chunk)
            await self.session.speak(text)

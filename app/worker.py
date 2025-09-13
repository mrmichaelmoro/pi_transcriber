import os
import time
import json
from vosk import Model, KaldiRecognizer
from ctransformers import AutoModelForCausalLM
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import wave

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

JOB_QUEUE_DIR = os.path.join(PROJECT_ROOT, "job_queue")
TRANSCRIPTS_DIR = os.path.join(PROJECT_ROOT, "transcripts")

# Model paths - update if you placed them elsewhere
VOSK_MODEL_PATH = "/opt/models/vosk-model"
LLAMA_MODEL_PATH = "/opt/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

POLL_INTERVAL = 5  # Seconds to wait before checking for new jobs

# --- Model Initialization ---
print("Loading models...")
if not os.path.exists(VOSK_MODEL_PATH):
    raise FileNotFoundError(f"Vosk model not found at {VOSK_MODEL_PATH}")
vosk_model = Model(VOSK_MODEL_PATH)

llm = AutoModelForCausalLM.from_pretrained(LLAMA_MODEL_PATH, model_type="llama")
print("Models loaded successfully.")

def transcribe_audio(filepath):
    """Transcribes a WAV file using the Vosk model."""
    wf = wave.open(filepath, "rb")
    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
        raise TypeError("Audio file must be WAV format mono 16-bit.")

    rec = KaldiRecognizer(vosk_model, wf.getframerate())
    rec.SetWords(True)

    full_transcript = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            full_transcript += result.get("text", "") + " "

    result = json.loads(rec.FinalResult())
    full_transcript += result.get("text", "")
    return full_transcript.strip()

def analyze_text(text):
    """Generates a summary and key points from text using the Llama model."""
    prompt = f"""
    Analyze the following transcript. Provide a concise one-paragraph summary and then list the top 3-5 key points as a bulleted list.

    Transcript:
    "{text}"

    Analysis:
    """
    print("Generating analysis with LLM...")
    analysis = llm(prompt, max_new_tokens=256, temperature=0.7)
    print("Analysis complete.")
    return analysis

def create_pdf(transcript, analysis, output_path):
    """Creates a PDF document from the transcript and analysis."""
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Audio Transcription and Analysis", styles['h1']))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Full Transcript", styles['h2']))
    story.append(Paragraph(transcript.replace("\n", "<br/>"), styles['BodyText']))
    story.append(Spacer(1, 24))

    story.append(Paragraph("AI-Generated Analysis", styles['h2']))
    story.append(Paragraph(analysis.replace("\n", "<br/>"), styles['BodyText']))

    doc.build(story)
    print(f"PDF generated at {output_path}")

def process_job(filepath):
    """The main processing pipeline for a single audio file."""
    try:
        print(f"Processing job: {os.path.basename(filepath)}")
        
        # 1. Transcribe
        transcript = transcribe_audio(filepath)
        if not transcript:
            print("Transcription returned no text. Aborting job.")
            return

        # 2. Analyze
        analysis = analyze_text(transcript)

        # 3. Generate PDF
        pdf_filename = os.path.basename(filepath).replace(".wav", ".pdf")
        pdf_path = os.path.join(TRANSCRIPTS_DIR, pdf_filename)
        create_pdf(transcript, analysis, pdf_path)

    finally:
        # 5. Delete original .wav file
        os.remove(filepath)
        print(f"Deleted job file: {os.path.basename(filepath)}")

if __name__ == "__main__":
    os.makedirs(JOB_QUEUE_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    
    print("Worker started. Monitoring job queue...")
    while True:
        jobs = [f for f in os.listdir(JOB_QUEUE_DIR) if f.endswith(".wav")]
        if jobs:
            job_file = os.path.join(JOB_QUEUE_DIR, jobs[0])
            process_job(job_file)
        else:
            time.sleep(POLL_INTERVAL)
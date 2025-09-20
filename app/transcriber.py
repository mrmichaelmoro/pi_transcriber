import RPi.GPIO as GPIO
import pyaudio
import wave
import time
import os
import uuid
import json
from datetime import datetime

# --- Configuration ---
SWITCH_PIN = 23
LED_PIN = 24

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOB_QUEUE_DIR = os.path.join(os.path.dirname(BASE_DIR), "job_queue")

# PyAudio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

# --- GPIO Setup ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LED_PIN, GPIO.OUT)

def blink_led(duration, interval=0.1):
    """Blinks the LED for a given duration."""
    end_time = time.time() + duration
    while time.time() < end_time:
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(interval)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(interval)

def record_audio():
    """Records audio while the switch is active and saves it to the job queue."""
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    print("Recording started...")
    frames = []
    
    # Start LED blinking
    GPIO.output(LED_PIN, GPIO.HIGH)

    while GPIO.input(SWITCH_PIN) == GPIO.LOW: # Assuming switch pulls to ground when active
        data = stream.read(CHUNK)
        frames.append(data)

    # Stop LED
    GPIO.output(LED_PIN, GPIO.LOW)
    print("Recording stopped.")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    # --- Create a proper meeting structure, same as web upload ---
    # 1. Create a new meeting structure
    meeting_id = f"{uuid.uuid4().hex}"
    transcripts_dir = os.path.join(PROJECT_ROOT, "transcripts")
    meeting_path = os.path.join(transcripts_dir, meeting_id)
    os.makedirs(os.path.join(meeting_path, 'attachments'), exist_ok=True)

    # 2. Save the audio file
    now = datetime.now()
    audio_basename = f"rec_{now.strftime('%Y%m%d_%H%M%S')}.wav"
    audio_path = os.path.join(meeting_path, audio_basename)
    with wave.open(audio_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    
    # 3. Create metadata.json
    metadata = {
        "name": f"Recording from {now.strftime('%Y-%m-%d %H:%M')}",
        "date": now.strftime('%Y-%m-%d'),
        "audio_filename": audio_basename
    }
    with open(os.path.join(meeting_path, 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)

    # 4. Create a job file in the queue
    os.makedirs(JOB_QUEUE_DIR, exist_ok=True)
    with open(os.path.join(JOB_QUEUE_DIR, f"{meeting_id}.job"), 'w') as f:
        f.write(meeting_id)

    print(f"Created job {meeting_id} for recording {audio_basename}")

if __name__ == "__main__":
    print("Hardware listener started. Waiting for switch...")
    try:
        while True:
            # Wait for the switch to be activated (pulled to LOW)
            GPIO.wait_for_edge(SWITCH_PIN, GPIO.FALLING)
            time.sleep(0.2) # Debounce
            record_audio()
            time.sleep(0.5) # Wait a bit before listening for the next press
    except KeyboardInterrupt:
        print("Exiting hardware listener.")
    finally:
        GPIO.cleanup()
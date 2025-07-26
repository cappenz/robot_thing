import os
import openai
import collections
import time
import datetime
import pyaudio
import numpy as np
import scipy.io.wavfile
import serial
import re
from math import radians, sin, cos, atan2, degrees
from openwakeword.model import Model
from faster_whisper import WhisperModel
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from geopy.geocoders import Nominatim

# === CONFIGURATION ===
OPENAI_API_KEY = ""#put your openai api key here
elevenlabs_api_key = ""#put your elevenlabs api key here
OUTPUT_DIR           = "./tmp"
THRESHOLD            = 0.8
COOLDOWN             = 4
SAVE_DELAY         = 5    # ← add this line
RATE_WAKE            = 16000
CHUNK_WAKE           = 512

# Base location (for bearing calculations)
BASE_LAT, BASE_LON = 0,0 #put your base location here

# Initialize clients
client = openai.OpenAI(api_key=OPENAI_API_KEY)
whisper        = WhisperModel("tiny", device="cpu")
elevenlabs     = ElevenLabs(api_key=elevenlabs_api_key)
geolocator     = Nominatim(user_agent="country-coords-script")


# === Helper functions ===

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Return bearing in degrees clockwise from north."""
    dLon = radians(lon2 - lon1)
    φ1, φ2 = radians(lat1), radians(lat2)
    x = sin(dLon) * cos(φ2)
    y = cos(φ1)*sin(φ2) - sin(φ1)*cos(φ2)*cos(dLon)
    θ = atan2(x, y)
    return (degrees(θ) + 360) % 360

def bearing_to_servo1(bearing):
    """
    Map bearing→servo1 angle:
      90° = north,
       0° = east (full right),
     180° = west (full left).
    """
    angle = 90 - bearing
    if angle < 0:
        angle += 360
    return int(max(0, min(180, angle)))

def handle_point_command(text, cur1, cur2):
    """
    If text contains "point to X" or "point at X",
    geocode X and compute new servo angles.
    """
    m = re.search(r"point (?:to|at) (.+)", text, re.IGNORECASE)
    if not m:
        return None
    location = m.group(1).strip()
    loc = geolocator.geocode(location, exactly_one=True, language='en')
    if not loc:
        raise ValueError(f"Couldn’t find {location!r}")
    lat, lon = loc.latitude, loc.longitude
    bearing = calculate_bearing(BASE_LAT, BASE_LON, lat, lon)
    s1 = bearing_to_servo1(bearing)
    s2 = cur2  # keep tilt unchanged (or set a default)
    return s1, s2

def transcribe_audio(path):
    segments, _ = whisper.transcribe(path)
    return " ".join(s.text for s in segments).strip()

def set_servo_angle(servo_name, angle):
    print(f"[SIM] {servo_name} → {angle}°")

def execute_servo_angles(a1, a2):
    global servo1_angle, servo2_angle
    servo1_angle, servo2_angle = a1, a2
    set_servo_angle("Servo1", a1)
    set_servo_angle("Servo2", a2)
    print(f"→ New state: 1={a1}°, 2={a2}°")
    try:
        ser = serial.Serial('/dev/cu.usbmodem11301', 115200)
        def send(cmd):
            ser.write(f"{cmd}\r\n".encode())
            print(ser.readline().decode().strip())
        send(f"servo1 {a1}")
        send(f"servo2 {a2}")
        ser.close()
    except Exception as e:
        print(f"[Serial Error] {e}")

def interpret_robot_command(text, cur1, cur2):
    # 1) Direct "point to ..."?
    direct = handle_point_command(text, cur1, cur2)
    if direct:
        return direct

    # 2) Otherwise, fallback to LLM
    system_prompt = (
        "You control a 2‑servo robotic arm."
        "You are JARVIS from Iron Man."
        "Servo1 (0–180°) swings left/right; 0° is full right, 180° full left.  "
        "Servo2 (0–90°) moves up/down; 0° is down, 90° is up.  "
        "Facing 90° is north; you are at 42.405547,-71.120259.  "
        "If asked a question, reply with 'knowledge:' plus the answer, addressed 'sir' as JARVIS."
        "ONLY TALK IF YOU FIND IT NECESSARY otherwise return a space"
        "If asked to point to a location, DO NOT speak—just compute the angles.  "
        "Respond only as:\n"
        "servo1: <angle>\n"
        "servo2: <angle>\n"
    )
    user_prompt = (
        f"Current positions:\n"
        f"servo1: {cur1}\n"
        f"servo2: {cur2}\n\n"
        f"User: {text}"
    )
    resp = client.chat.completions.create(        
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        temperature=0
    ).choices[0].message.content.strip().lower()

    if resp.startswith("knowledge"):
        answer = resp.replace("knowledge:", "").strip()
        audio = elevenlabs.text_to_speech.convert(
            text=answer,
            voice_id="MAnGpyr8aoBY5ZhzgIss",
            model_id="eleven_turbo_v2_5"
        )
        play(audio)
        return cur1, cur2

    # Parse servo angles from LLM output
    lines = [l for l in resp.splitlines() if l.startswith("servo")]
    try:
        s1 = int(lines[0].split(":")[1])
        s2 = int(lines[1].split(":")[1])
    except:
        print("⚠️  Parsing failed; keeping previous angles.")
        return cur1, cur2

    return max(0, min(180, s1)), max(0, min(90, s2))

def process_file(path):
    print("🔄 Transcribing…")
    txt = transcribe_audio(path)
    print("📝", txt)
    print("🤖 Interpreting…")
    new1, new2 = interpret_robot_command(txt, servo1_angle, servo2_angle)
    print("⚙️ Moving servos…")
    execute_servo_angles(new1, new2)

def capture_loop():
    audio     = pyaudio.PyAudio()
    stream    = audio.open(format=pyaudio.paInt16,
                           channels=1,
                           rate=RATE_WAKE,
                           input=True,
                           frames_per_buffer=CHUNK_WAKE)
    wake_model = Model(inference_framework="onnx")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    last_save = 0
    buffer    = collections.deque(maxlen=RATE_WAKE*SAVE_DELAY)

    print("🎧 Listening…")
    while True:
        data  = stream.read(CHUNK_WAKE, exception_on_overflow=False)
        frame = np.frombuffer(data, np.int16)
        buffer.extend(frame)
        pred  = wake_model.predict(frame)

        for mdl, score in pred.items():
            if score >= THRESHOLD and time.time() - last_save > COOLDOWN:
                last_save = time.time()
                ts        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fname     = f"{ts}_{mdl}.wav"
                path      = os.path.join(OUTPUT_DIR, fname)

                # record a few seconds
                frames = []
                num_chunks = int(RATE_WAKE / CHUNK_WAKE * SAVE_DELAY)
                for _ in range(num_chunks):
                    data2 = stream.read(CHUNK_WAKE, exception_on_overflow=False)
                    frames.append(np.frombuffer(data2, np.int16))

                audio_data = np.concatenate(frames)
                scipy.io.wavfile.write(path, RATE_WAKE, audio_data)
                print(f"🔔 Wakeword! Saved “{fname}”")
                process_file(path)

if __name__ == "__main__":
    # Initialize servo positions
    servo1_angle, servo2_angle = 90, 60
    capture_loop()

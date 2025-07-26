🤖 Voice-Controlled Servo Robot Assistant – README
This project creates a voice-activated, AI-powered robotic assistant that:

  -- Listens for a wake word
  
  -- Records and transcribes your speech
  
  -- Responds like JARVIS from Iron Man
  
  -- Moves two servos to indicate direction or answer
  
  -- Can point toward real-world locations using geolocation and bearing calculations
  
  -- Speaks responses using ElevenLabs if needed

⚙️ Features
✅ Wake word detection
✅ Voice transcription (via Faster-Whisper)
✅ Natural language understanding (via OpenAI GPT-4o-mini)
✅ Location geocoding with Nominatim
✅ Servo direction calculation and communication via serial
✅ Text-to-speech audio replies with ElevenLabs
✅ Smooth continuous microphone input loop

🧰 Requirements
Install dependencies:

uv  add openai faster-whisper elevenlabs pyaudio numpy scipy geopy openwakeword
#i use uv but i think you can use pip too
Also ensure:

Python 3.8+

ffmpeg is installed (needed by Whisper)


🔐 API Keys Required
Add your keys at the top of the script:

OPENAI_API_KEY – from OpenAI

elevenlabs_api_key – from ElevenLabs

🛠 Hardware Setup
Make sure your hardware it set up correctly
![IMG_9249](https://github.com/user-attachments/assets/afbdb8ce-63d5-47fb-9cbd-07a9c0a38016)

Servos:
Servo1: Pan left/right (0–180°)
Servo2: Tilt up/down (0–90°)

Microcontroller:
Connect via USB and match the serial port in the code:

ser = serial.Serial('/dev/cu.usbmodem11301', 115200)

Serial Command Format:
Expected commands from Python:

servo1 <angle>
servo2 <angle>

Update your microcontroller firmware to parse and apply these.
You might want to use Thonny to connect to it

🌍 Location Pointing
You can say:

“Point to Paris”

It will:

  Geocode the location
  
  Calculate bearing from your BASE_LAT and BASE_LON
  
  Rotate the servo to match the direction (like a compass needle)

Set your base location:

  BASE_LAT, BASE_LON = 38.9072, 77.0369   # Example: Washington D.C.

It needs to be pointing north as its 'center' for it to point accuratly as thats where i told it it was pointing in the code

You can change that along with the degree stoppers as currrently it cant point south/ 180 degrees from center

🎤 Wake Word + Voice Control
The system listens continuously using openwakeword, and on activation:

  Records 5 seconds of audio
  
  Transcribes with Faster-Whisper
  
  Interprets command via LLM
  
  Speaks if needed, moves servos otherwise

🧠 Sample Commands
You need to say "Hey Jarvis" but then you can follow by:

  “Point to London”
  
  “Move your head up”
  
  “What’s the weather like?”
  
  “Turn left”
  
  “Look north”

JARVIS will either respond with audio (knowledge:) or just move silently if it's a directional command.


🧙🏻 Summary
This project is like your own mini JARVIS:
  
  Understands voice
  
  Moves servos intelligently
  
  Responds to natural language
  
  Points toward global locations
  
  Gives verbal responses when needed


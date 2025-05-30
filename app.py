import os
import uuid
import subprocess
import requests
import json
import streamlit as st
from dotenv import load_dotenv

APIKEY = os.getenv('APIKEY')


# Load environment
load_dotenv()
st.set_page_config(page_title="Audio Transkription & Zusammenfassung", layout="centered")

# Optionaler Zugangsschutz
if APIKEY:
    with st.sidebar:
        st.markdown("🔐 **Zugang geschützt**")
        user_key = st.text_input("API-Key eingeben", type="password")
        if user_key != APIKEY:
            st.warning("Zugang verweigert. Gültigen API-Key eingeben.")
            st.stop()

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER', 'outputs')
WHISPER_EXECUTABLE = os.getenv('WHISPER_EXECUTABLE', './main')
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'models/ggml-base.en.bin')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def sanitize_transcript(text: str) -> str:
    replacements = {
        '[': '⟦', ']': '⟧',
        '<': '‹', '>': '›',
        '{': '｛', '}': '｝',
        '"': '“', "'": "’",
        '`': 'ˋ', '\\': '⧵',
        '*': '∗', '_': '‗', '~': '∼',
        '|': '∣', '#': '♯', '$': '﹩', '&': '＆'
    }
    return ''.join(replacements.get(c, c) for c in text)

def ollama_summarize(transcript, prompt_addon):
    full_prompt = f"Hier ist ein Transkript:\n\n{transcript}\n\n{prompt_addon}"

    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "Fasse das folgende Transkript hilfreich zusammen."},
                {"role": "user", "content": full_prompt}
            ]
        },
        stream=True
    )
    response.raise_for_status()

    content = ""
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8'))
            if 'message' in data and 'content' in data['message']:
                content += data['message']['content']

    return content.strip()

def convert_to_wav(input_path, output_path):
    subprocess.run([
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
        output_path
    ], check=True)

def transcribe(wav_path, output_txt_path):
    subprocess.run([
        WHISPER_EXECUTABLE,
        '-nt',
        '-l', 'auto',
        '-m', WHISPER_MODEL,
        '-f', wav_path,
        '-otxt',
        '-of', output_txt_path
    ], check=True)

st.title("🎙️ Audio Transkribieren & Zusammenfassen mit Ollama")

uploaded_file = st.file_uploader("Audio-Datei hochladen", type=["mp3", "wav", "m4a"])
prompt_addon = st.text_area("Zusätzlicher Prompt (z. B. 'Fasse als Meetingprotokoll zusammen')", "")

if st.button("Verarbeiten") and uploaded_file:
    task_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{uploaded_file.name}")
    wav_path = input_path.rsplit('.', 1)[0] + ".wav"
    txt_base = os.path.join(OUTPUT_FOLDER, f"{task_id}_transcript")  # ohne .txt

    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    progress = st.progress(0, text="🔁 Starte Verarbeitung...")

    try:
        progress.progress(10, "🎧 Konvertiere nach WAV...")
        convert_to_wav(input_path, wav_path)

        progress.progress(40, "📝 Transkribiere mit Whisper...")
        transcribe(wav_path, txt_base)  # ohne .txt

        progress.progress(60, "📄 Lade Transkript...")
        with open(f"{txt_base}.txt", "r", encoding="utf-8") as f:
            transcript = f.read()

        transcript = sanitize_transcript(transcript)

        st.subheader("📄 Transkript (Vorschau)")
        st.text_area("Transkript", transcript, height=300)

        progress.progress(80, "🧠 Sende an Ollama...")
        summary = ollama_summarize(transcript, prompt_addon)

        progress.progress(100, "✅ Fertig!")

        st.subheader("📝 Zusammenfassung")
        st.write(summary)

    except Exception as e:
        progress.empty()
        st.error(f"❌ Fehler bei der Verarbeitung: {e}")

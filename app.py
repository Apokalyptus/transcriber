import os
import uuid
import subprocess
import requests
import json
import streamlit as st
from dotenv import load_dotenv

# Load environment
load_dotenv()
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
        'nt',
        '-l', 'auto',
        '-m', WHISPER_MODEL,
        '-f', wav_path,
        '-otxt',
        '-of', output_txt_path
    ], check=True)

st.set_page_config(page_title="Audio Transkription & Zusammenfassung", layout="centered")
st.title("🎙️ Audio Transkribieren & Zusammenfassen mit Ollama")

uploaded_file = st.file_uploader("Audio-Datei hochladen", type=["mp3", "wav", "m4a"])
prompt_addon = st.text_area("Zusätzlicher Prompt (z. B. 'Fasse als Meetingprotokoll zusammen')", "")

if st.button("Verarbeiten") and uploaded_file:
    task_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{uploaded_file.name}")
    wav_path = input_path.rsplit('.', 1)[0] + ".wav"
    txt_path = os.path.join(OUTPUT_FOLDER, f"{task_id}_transcript")

    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    with st.spinner("Konvertiere und transkribiere..."):
        convert_to_wav(input_path, wav_path)
        transcribe(wav_path, txt_path)

    with open(f"{txt_path}.txt", "r", encoding="utf-8") as f:
        transcript = f.read()

    transcript = sanitize_transcript(transcript)

    with st.spinner("Sende an Ollama..."):
        summary = ollama_summarize(transcript, prompt_addon)

    st.subheader("📝 Zusammenfassung")
    st.write(summary)

    st.subheader("📄 Transkript")
    st.text_area("Transkript", transcript, height=300)

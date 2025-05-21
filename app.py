import os
import subprocess
import threading
import uuid
from openai import OpenAI
from queue import Queue
from flask import Flask, request, render_template, jsonify, redirect, url_for, session, abort
from dotenv import load_dotenv


load_dotenv()

# Konfiguration über Umgebungsvariablen
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER', 'outputs')
WHISPER_EXECUTABLE = os.getenv('WHISPER_EXECUTABLE', './whisper-cli')
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'models/ggml-large-v3-turbo.bin')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
APIKEY = os.getenv('APIKEY')  # Optionaler API-Schlüssel
SECRET_KEY = os.getenv('SECRET_KEY', 'supersecret')  # Für Sitzungen

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Task-Queue und Ergebnisse
task_queue = Queue()
task_results = {}

def worker():
    while True:
        task_id, file_path, prompt_addon = task_queue.get()
        try:
            wav_path = file_path.rsplit('.', 1)[0] + '.wav'
            subprocess.run([
            'ffmpeg', '-y',
            '-i', file_path,
            '-ar', '16000',
            '-ac', '1',
            '-c:a', 'pcm_s16le',
            wav_path
            ], check=True)
            
            result_path = os.path.join(OUTPUT_FOLDER, f"{task_id}_transcript.txt")
            subprocess.run([
                WHISPER_EXECUTABLE,
                '-m', WHISPER_MODEL,
                '-f', wav_path,
                '-otxt',
                '-of', result_path
            ], check=True)

            with open(result_path + '.txt', 'r', encoding='utf-8') as f:
                transcript = f.read()

            user_prompt = f"Hier ist ein Transkript:\n\n{transcript}\n\n{prompt_addon}"

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes transcriptions."},
                    {"role": "user", "content": user_prompt}
                ]
            )

            summary = response.choices[0].message.content
            
            task_results[task_id] = {
                "status": "done",
                "summary": summary,
                "transcript": transcript
            }

        except Exception as e:
            task_results[task_id] = {
                "status": "error",
                "message": str(e)
            }

        task_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

def check_access():
    if not APIKEY:
        return  # Kein Schutz aktiv
    if not session.get('authenticated'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not APIKEY:
        return redirect(url_for('index'))  # Kein Schutz aktiv

    if request.method == 'POST':
        key = request.form.get('apikey', '')
        if key == APIKEY:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Ungültiger API-Schlüssel")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    access = check_access()
    if access:
        return access
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    access = check_access()
    if access:
        return access

    file = request.files['file']
    prompt_addon = request.form.get('prompt_addon', '')

    if file:
        task_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
        file.save(file_path)

        task_results[task_id] = {"status": "queued"}
        task_queue.put((task_id, file_path, prompt_addon))

        return jsonify({
            "message": "Upload empfangen. Verarbeitung im Hintergrund.",
            "task_id": task_id,
            "check_url": f"/result/{task_id}"
        })

    return "Keine Datei hochgeladen", 400

@app.route('/result/<task_id>', methods=['GET'])
def result(task_id):
    access = check_access()
    if access:
        return access

    result = task_results.get(task_id)
    if not result:
        return jsonify({"status": "not_found"}), 404

    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

import os
import uuid
from flask import Flask, jsonify, request, send_from_directory, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

TRANSCRIPTS_DIR = os.path.join(PROJECT_ROOT, "transcripts")
JOB_QUEUE_DIR = os.path.join(PROJECT_ROOT, "job_queue")
ALLOWED_EXTENSIONS = {'wav'}

os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
os.makedirs(JOB_QUEUE_DIR, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/transcripts', methods=['GET'])
def list_transcripts():
    """Returns a list of available PDF transcripts."""
    try:
        files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith('.pdf')]
        files.sort(key=lambda name: os.path.getmtime(os.path.join(TRANSCRIPTS_DIR, name)), reverse=True)
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcripts/<path:filename>', methods=['GET'])
def download_transcript(filename):
    """Serves a specific transcript file for download."""
    try:
        return send_from_directory(TRANSCRIPTS_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

@app.route('/api/transcripts/<path:filename>', methods=['DELETE'])
def delete_transcript(filename):
    """Deletes a specific transcript file."""
    try:
        filepath = os.path.join(TRANSCRIPTS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({"success": f"File '{filename}' deleted."}), 200
        else:
            return jsonify({"error": "File not found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handles audio file uploads and places them in the job queue."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        # Create a unique filename to avoid conflicts
        original_filename = secure_filename(file.filename)
        unique_filename = f"upload_{uuid.uuid4().hex[:8]}_{original_filename}"
        filepath = os.path.join(JOB_QUEUE_DIR, unique_filename)
        file.save(filepath)
        return jsonify({"success": f"File '{original_filename}' uploaded and queued for processing."}), 201
    return jsonify({"error": "File type not allowed. Please upload a .wav file."}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
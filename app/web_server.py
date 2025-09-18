import os
import uuid
import json
import re
import subprocess
from flask import Flask, jsonify, request, send_from_directory, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

TRANSCRIPTS_DIR = os.path.join(PROJECT_ROOT, "transcripts")
JOB_QUEUE_DIR = os.path.join(PROJECT_ROOT, "job_queue")
ALLOWED_EXTENSIONS = {'wav', 'm4a'}

os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
os.makedirs(JOB_QUEUE_DIR, exist_ok=True)
WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_meeting_path(meeting_id):
    """Constructs the path to a meeting directory."""
    return os.path.join(TRANSCRIPTS_DIR, meeting_id)

@app.route('/api/transcripts', methods=['GET'])
def list_transcripts():
    """Returns a list of all meetings with their metadata."""
    try:
        meetings = []
        for meeting_id in os.listdir(TRANSCRIPTS_DIR):
            meeting_path = get_meeting_path(meeting_id)
            if os.path.isdir(meeting_path):
                metadata_path = os.path.join(meeting_path, 'metadata.json')
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        metadata['id'] = meeting_id
                        # Check for PDF existence
                        pdf_filename = f"{metadata.get('audio_basename', 'transcript')}.pdf"
                        metadata['pdf_exists'] = os.path.exists(os.path.join(meeting_path, pdf_filename))
                        meetings.append(metadata)
        
        # Sort by date, descending
        meetings.sort(key=lambda m: m.get('date', '1970-01-01'), reverse=True)
        return jsonify(meetings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcripts/<meeting_id>', methods=['PUT'])
def update_transcript_metadata(meeting_id):
    """Updates the metadata for a specific meeting."""
    data = request.get_json()
    meeting_path = get_meeting_path(meeting_id)
    metadata_path = os.path.join(meeting_path, 'metadata.json')

    if not os.path.exists(metadata_path):
        return jsonify({"error": "Meeting not found."}), 404

    try:
        with open(metadata_path, 'r+') as f:
            metadata = json.load(f)
            metadata['name'] = data.get('name', metadata['name'])
            metadata['date'] = data.get('date', metadata['date'])
            f.seek(0)
            json.dump(metadata, f, indent=2)
            f.truncate()
        return jsonify({"success": "Metadata updated."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcripts/<meeting_id>/<filename>', methods=['GET'])
def download_transcript(meeting_id, filename):
    """Serves a specific transcript file for download."""
    try:
        meeting_path = get_meeting_path(meeting_id)
        return send_from_directory(meeting_path, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

@app.route('/api/transcripts/<meeting_id>', methods=['DELETE'])
def delete_transcript(meeting_id):
    """Deletes an entire meeting directory."""
    try:
        meeting_path = get_meeting_path(meeting_id)
        if os.path.isdir(meeting_path):
            import shutil
            shutil.rmtree(meeting_path)
            return jsonify({"success": f"Meeting '{meeting_id}' deleted."}), 200
        else:
            return jsonify({"error": "File not found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handles audio file uploads, creates a meeting structure, and queues it."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        meeting_name = request.form.get('name', 'Untitled Meeting')
        meeting_date = request.form.get('date', '1970-01-01')

        # 1. Create a new meeting structure
        meeting_id = f"{uuid.uuid4().hex}"
        meeting_path = get_meeting_path(meeting_id)
        os.makedirs(os.path.join(meeting_path, 'attachments'), exist_ok=True)

        # 2. Save the audio file
        audio_basename = secure_filename(file.filename)
        audio_path = os.path.join(meeting_path, audio_basename)
        file.save(audio_path)

        # 3. Create metadata.json
        metadata = {
            "name": meeting_name,
            "date": meeting_date,
            "audio_filename": audio_basename
        }
        with open(os.path.join(meeting_path, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)

        # 4. Create a job file in the queue
        with open(os.path.join(JOB_QUEUE_DIR, f"{meeting_id}.job"), 'w') as f:
            f.write(meeting_id)

        return jsonify({"success": f"Meeting '{meeting_name}' created and queued for processing."}), 201

    return jsonify({"error": "File type not allowed. Please upload a .wav or .m4a file."}), 400

# --- Wi-Fi Management API ---

@app.route('/api/wifi/scan', methods=['GET'])
def wifi_scan():
    """Scans for Wi-Fi networks on wlan1."""
    try:
        # Use iwlist to scan for networks. Requires sudo permissions.
        scan_output = subprocess.check_output(['sudo', 'iwlist', 'wlan1', 'scan'], text=True)
        ssids = re.findall(r'ESSID:"([^"]+)"', scan_output)
        # Remove duplicates and empty strings
        unique_ssids = sorted(list(set(filter(None, ssids))))
        return jsonify(unique_ssids)
    except subprocess.CalledProcessError as e:
        if "No such device" in e.stderr:
            return jsonify({"error": "Secondary Wi-Fi adapter (wlan1) not found."}), 500
        if "Network is down" in e.stderr:
             return jsonify({"error": "Wi-Fi interface wlan1 is down."}), 500
        return jsonify({"error": f"Failed to scan for networks: {e.stderr}"}), 500
    except FileNotFoundError:
        return jsonify({"error": "iwlist command not found. Is wireless-tools installed?"}), 500

@app.route('/api/wifi/status', methods=['GET'])
def wifi_status():
    """Gets the current status of the wlan1 interface."""
    try:
        status_output = subprocess.check_output(['sudo', 'wpa_cli', '-i', 'wlan1', 'status'], text=True)
        ip_output = subprocess.check_output(['sudo', 'ip', 'addr', 'show', 'wlan1'], text=True)

        ssid_match = re.search(r'^ssid=(.*)$', status_output, re.MULTILINE)
        ip_match = re.search(r'inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', ip_output)
        
        ssid = ssid_match.group(1) if ssid_match else "Not connected"
        ip_address = ip_match.group(1) if ip_match else "N/A"

        return jsonify({"ssid": ssid, "ip_address": ip_address})
    except (subprocess.CalledProcessError, FileNotFoundError):
        return jsonify({"ssid": "Not connected", "ip_address": "N/A"})

@app.route('/api/wifi/connect', methods=['POST'])
def wifi_connect():
    """Connects wlan1 to a new Wi-Fi network."""
    data = request.get_json()
    ssid = data.get('ssid')
    password = data.get('password')

    if not ssid or not password:
        return jsonify({"error": "SSID and password are required."}), 400

    try:
        # Read the current wpa_supplicant.conf
        with open(WPA_SUPPLICANT_CONF, 'r') as f:
            conf_content = f.read()

        # Remove any existing network block for the same SSID to avoid duplicates
        # This regex is a bit complex to handle nested braces
        conf_content = re.sub(r'network\s*=\s*{\s*ssid\s*=\s*"' + re.escape(ssid) + r'".*?^\s*}', '', conf_content, flags=re.DOTALL | re.MULTILINE)
        
        # Generate the new network block using wpa_passphrase for security
        network_block = subprocess.check_output(['wpa_passphrase', ssid, password], text=True)
        
        # Append the new network block
        with open(WPA_SUPPLICANT_CONF, 'w') as f:
            f.write(conf_content.strip() + "\n\n" + network_block)

        # Tell wpa_supplicant to re-read the configuration
        subprocess.check_call(['sudo', 'wpa_cli', '-i', 'wlan1', 'reconfigure'])

        return jsonify({"success": f"Attempting to connect to '{ssid}'. Check status in a few moments."})

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Failed to configure Wi-Fi: {e.stderr}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# --- Attachment Management API ---

@app.route('/api/transcripts/<meeting_id>/attachments', methods=['GET'])
def get_attachments(meeting_id):
    """Lists attachments for a specific meeting."""
    attachments_path = os.path.join(get_meeting_path(meeting_id), 'attachments')
    if not os.path.isdir(attachments_path):
        return jsonify({"error": "Meeting not found or has no attachments folder."}), 404
    files = os.listdir(attachments_path)
    return jsonify(files)

@app.route('/api/transcripts/<meeting_id>/attachments', methods=['POST'])
def add_attachment(meeting_id):
    """Uploads an attachment to a specific meeting."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    attachments_path = os.path.join(get_meeting_path(meeting_id), 'attachments')
    if not os.path.isdir(attachments_path):
        return jsonify({"error": "Meeting not found."}), 404

    filename = secure_filename(file.filename)
    file.save(os.path.join(attachments_path, filename))
    return jsonify({"success": f"Attachment '{filename}' uploaded."}), 201

@app.route('/api/transcripts/<meeting_id>/attachments/<filename>', methods=['DELETE'])
def delete_attachment(meeting_id, filename):
    """Deletes a specific attachment."""
    filepath = os.path.join(get_meeting_path(meeting_id), 'attachments', secure_filename(filename))
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"success": "Attachment deleted."})
    return jsonify({"error": "Attachment not found."}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
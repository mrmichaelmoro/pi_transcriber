import os
import uuid
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
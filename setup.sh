#!/bin/bash

# ==============================================================================
# Setup Script for Headless Offline Transcription Appliance
# ==============================================================================
# This script automates the setup process described in setup_guide.md.
# It should be run on a fresh Raspberry Pi OS (64-bit Lite) installation.
#
# To run:
# 1. Make the script executable: chmod +x setup.sh
# 2. Run with sudo: sudo ./setup.sh
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status.

# Check if running as root/sudo
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script with sudo: sudo ./setup.sh"
  exit 1
fi

# --- Configuration ---
# The dedicated non-privileged user to run the application services.
SERVICE_USER="transcribe"

# Wi-Fi Access Point Settings
AP_SSID="TranscriberAP"
AP_PASSWORD="transcriber" # Must be 8-63 characters
AP_IP="192.168.4.1"
WIFI_COUNTRY="US" # Set your 2-letter country code here (e.g., GB, DE, CA)

# Directories
APP_DIR="/home/${SERVICE_USER}/transcriber-app"
MODEL_DIR="/opt/models"

echo "--- Starting Transcription Appliance Setup ---"
echo "Services will be run by the '${SERVICE_USER}' user."

# --- 1. System Update and Prerequisite Installation ---
echo ">>> Step 1: Updating system and installing dependencies..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y nginx python3-pip python3-pyaudio git unzip ffmpeg git-lfs hostapd dnsmasq
echo ">>> Step 1: Complete."

# --- 2. Download and Set Up AI Models ---
echo ">>> Step 2: Downloading and setting up AI models..."
sudo mkdir -p "${MODEL_DIR}"

# Run model downloads in a subshell to isolate the 'cd' command
(
    cd "${MODEL_DIR}"
    # Download and unzip Vosk model
    if [ ! -d "vosk-model" ]; then
        echo "Downloading Vosk model..."
        sudo wget -q --show-progress https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
        sudo unzip -q vosk-model-small-en-us-0.15.zip
        sudo mv vosk-model-small-en-us-0.15 vosk-model
        sudo rm vosk-model-small-en-us-0.15.zip
        echo "Vosk model installed."
    else
        echo "Vosk model already exists. Skipping download."
    fi

    # Download TinyLlama model
    LLAMA_MODEL_FILE="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
    if [ ! -f "${LLAMA_MODEL_FILE}" ]; then
        echo "Downloading TinyLlama model..."
        sudo wget -q --show-progress -O "${LLAMA_MODEL_FILE}" https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
        echo "TinyLlama model installed."
    else
        echo "TinyLlama model already exists. Skipping download."
    fi
)

# Set correct permissions for the models directory.
# The service user needs to read these. Making them world-readable is a safe way to do this.
sudo chmod -R 755 "${MODEL_DIR}"
echo ">>> Step 2: Complete."

# --- 3. Create Service User ---
echo ">>> Step 3: Creating non-privileged user '${SERVICE_USER}'..."
if id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    echo "User '${SERVICE_USER}' already exists. Skipping creation."
else
    # Create a system user with a home directory but no login shell
    sudo useradd -r -s /bin/false -m -d "/home/${SERVICE_USER}" "${SERVICE_USER}"
    echo "User '${SERVICE_USER}' created."
fi
echo ">>> Step 3: Complete."

# --- 4. Copy Application Files ---
echo ">>> Step 4: Copying application files..."
# Determine the directory where the script is located (the repo root)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

sudo mkdir -p "${APP_DIR}"
sudo rsync -a --exclude='.git' --exclude='setup.sh' "${SCRIPT_DIR}/" "${APP_DIR}/"
sudo chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

# --- Grant Web Server Access ---
echo "Granting Nginx permissions to access web UI files..."
sudo usermod -a -G "${SERVICE_USER}" www-data
sudo chmod 750 "/home/${SERVICE_USER}"
sudo chmod -R 750 "${APP_DIR}"

echo ">>> Step 4: Complete."

# --- 5. Install Python Libraries ---
echo ">>> Step 5: Installing Python libraries..."
# Install Python packages system-wide for all users and services to access.
sudo pip3 install -r "${APP_DIR}/app/requirements.txt"
echo ">>> Step 5: Complete."

# --- 6. Configure Nginx ---
echo ">>> Step 6: Configuring Nginx..."
sudo rm -f /etc/nginx/sites-enabled/default

# Use sed to replace the placeholder root directory with the actual APP_DIR
NGINX_CONF_TARGET="/etc/nginx/sites-available/transcriber"
sudo sed "s|__APP_DIR__|${APP_DIR}|g" "${APP_DIR}/nginx/nginx.conf" > /tmp/transcriber.nginx
sudo mv /tmp/transcriber.nginx "${NGINX_CONF_TARGET}"

# Create symlink if it doesn't exist
if [ ! -L /etc/nginx/sites-enabled/transcriber ]; then
    sudo ln -s "${NGINX_CONF_TARGET}" /etc/nginx/sites-enabled/
fi

sudo nginx -t # Test configuration
sudo systemctl restart nginx
echo ">>> Step 6: Complete."

# --- 7. Create and Enable systemd Services ---
echo ">>> Step 7: Creating and enabling systemd services..."

# Create a helper function to generate service files
create_service_file() {
    SERVICE_FILE_PATH=$1
    DESCRIPTION=$2
    EXEC_START=$3
    AFTER=$4
    WORKING_DIR_LINE=""
    if [ ! -z "$5" ]; then
        WORKING_DIR_LINE="WorkingDirectory=$5"
    fi

    echo "Creating ${SERVICE_FILE_PATH}..."
    sudo bash -c "cat > ${SERVICE_FILE_PATH}" <<EOF
[Unit]
Description=${DESCRIPTION}
After=${AFTER}

[Service]
Type=simple
ExecStart=${EXEC_START}
Restart=on-failure
User=${SERVICE_USER}
${WORKING_DIR_LINE}

[Install]
WantedBy=multi-user.target
EOF
}

create_service_file "/etc/systemd/system/transcriber-hw.service" "Transcriber Hardware Service" "/usr/bin/python3 ${APP_DIR}/app/transcriber.py" "multi-user.target"
create_service_file "/etc/systemd/system/transcriber-worker.service" "Transcriber Worker Service" "/usr/bin/python3 ${APP_DIR}/app/worker.py" "multi-user.target"
create_service_file "/etc/systemd/system/transcriber-web.service" "Transcriber Web Service (Flask)" "/usr/bin/python3 ${APP_DIR}/app/web_server.py" "network.target" "${APP_DIR}/app"

echo "Reloading systemd, enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable transcriber-hw.service transcriber-worker.service transcriber-web.service
sudo systemctl start transcriber-hw.service transcriber-worker.service transcriber-web.service
echo ">>> Step 7: Complete."

echo "--- Setup is complete! ---"
echo "You can now access the web interface at http://<your-pi-ip-address>"
echo "If AP mode was enabled, connect to the '${AP_SSID}' Wi-Fi network."
echo "You will need to reboot for AP mode to take effect."

# --- 8. Sudoers for Network Management ---
echo ">>> Step 8: Granting network permissions to ${SERVICE_USER} for wlan0..."
SUDOERS_FILE="/etc/sudoers.d/010_${SERVICE_USER}-network"
sudo bash -c "cat > ${SUDOERS_FILE}" <<EOF
# Allow the ${SERVICE_USER} user to run specific network commands
${SERVICE_USER} ALL=(ALL) NOPASSWD: /sbin/iwlist wlan0 scan
${SERVICE_USER} ALL=(ALL) NOPASSWD: /sbin/wpa_cli -i wlan0 reconfigure
${SERVICE_USER} ALL=(ALL) NOPASSWD: /sbin/wpa_cli -i wlan0 status
${SERVICE_USER} ALL=(ALL) NOPASSWD: /sbin/ip addr show wlan0
EOF
sudo chmod 0440 "${SUDOERS_FILE}"
echo ">>> Step 8: Complete."
 
# --- 9. Enable Wi-Fi Radio ---
echo ">>> Step 9: Enabling Wi-Fi Radio..."
echo "Setting Wi-Fi Country to ${WIFI_COUNTRY} and unblocking interface."
# The raspi-config tool is not always present on lite images, install it if needed.
sudo apt-get install -y raspi-config
sudo raspi-config nonint do_wifi_country "${WIFI_COUNTRY}"
sudo rfkill unblock wifi
echo ">>> Step 9: Complete."

# --- 9. Configure Wi-Fi Access Point ---
echo ">>> Step 9: Configuring Wi-Fi Access Point..."

# Check if password is valid
if [ ${#AP_PASSWORD} -lt 8 ] || [ ${#AP_PASSWORD} -gt 63 ]; then
    echo "!!! WARNING: Wi-Fi password is not valid (must be 8-63 characters). Skipping AP setup."
    exit 0
fi

# 1. Configure dhcpcd to set a static IP for wlan0 using a drop-in config file
echo "Configuring static IP for wlan0..."
DHCPCD_CONF_DIR="/etc/dhcpcd.conf.d"
sudo mkdir -p "${DHCPCD_CONF_DIR}"
sudo bash -c "cat > ${DHCPCD_CONF_DIR}/wlan0-ap.conf" <<EOF
# Configuration for Access Point mode on wlan0
interface wlan0
    static ip_address=${AP_IP}/24
    nohook wpa_supplicant
EOF

# 2. Configure dnsmasq for DHCP
echo "Configuring dnsmasq..."
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
sudo bash -c "cat > /etc/dnsmasq.conf" <<EOF
# Listen only on the wlan0 interface for DHCP and DNS requests.
interface=wlan0
# Do not bind to the wildcard address. This ensures dnsmasq does not listen on any other interfaces.
bind-interfaces
# Set the DHCP range for the AP network.
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
# Provide the IP of the Pi as the DNS server for clients.
server=${AP_IP}
EOF

# 3. Configure hostapd
echo "Configuring hostapd..."
sudo bash -c "cat > /etc/hostapd/hostapd.conf" <<EOF
interface=wlan0
driver=nl80211
ssid=${AP_SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${AP_PASSWORD}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

echo "Enabling AP services..."
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq
echo ">>> Step 9: Complete. Please reboot the Raspberry Pi to activate the Access Point."

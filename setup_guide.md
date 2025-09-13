# Setup Guide

This guide details the steps to set up the Raspberry Pi from a fresh OS install to a fully functional transcription appliance.

### 1. Initial Pi Setup

1.  Install Raspberry Pi OS (64-bit Lite recommended) on your microSD card.
2.  Enable SSH and configure your Wi-Fi credentials.
3.  Boot the Pi, connect via SSH, and run updates:
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

### 2. Install System Dependencies

Install Nginx, Python, and other required system libraries.

```bash
sudo apt install -y nginx python3-pip python3-pyaudio git
```

### 3. Download AI Models

The appliance requires two offline models. These should be placed in a location accessible by the application, for example, `/opt/models`.

```bash
sudo mkdir -p /opt/models
cd /opt/models

# Download and unzip the Vosk model for transcription
sudo wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
sudo unzip vosk-model-small-en-us-0.15.zip
sudo mv vosk-model-small-en-us-0.15 vosk-model
sudo rm vosk-model-small-en-us-0.15.zip

# Download the TinyLlama model for analysis
sudo wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf

sudo chown -R $USER:$USER /opt/models
```

### 4. Clone the Application

Clone this repository to your Pi's home directory.

```bash
cd ~
git clone <your-repo-url> transcriber-app
cd transcriber-app
```

### 5. Install Python Libraries

Install the required Python packages using pip.

```bash
pip3 install -r app/requirements.txt
```

### 6. Configure Nginx

1.  Disable the default Nginx site:
    ```bash
    sudo rm /etc/nginx/sites-enabled/default
    ```
2.  Copy the provided `nginx.conf` to create a new site configuration:
    ```bash
    sudo cp ~/transcriber-app/nginx/nginx.conf /etc/nginx/sites-available/transcriber
    ```
3.  Enable your new site by creating a symbolic link:
    ```bash
    sudo ln -s /etc/nginx/sites-available/transcriber /etc/nginx/sites-enabled/
    ```
4.  Test the configuration and restart Nginx:
    ```bash
    sudo nginx -t
    sudo systemctl restart nginx
    ```

### 7. Create systemd Services

Create three separate `systemd` service files to manage the application components and ensure they run on boot.

**Create the files:**
```bash
sudo nano /etc/systemd/system/transcriber-hw.service
sudo nano /etc/systemd/system/transcriber-worker.service
sudo nano /etc/systemd/system/transcriber-web.service
```

**Paste the content for each file below.** Replace `<your_username>` with your actual username (e.g., `pi`).

<details>
<summary><code>transcriber-hw.service</code></summary>

```ini
[Unit]
Description=Transcriber Hardware Service
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/<your_username>/transcriber-app/app/transcriber.py
Restart=on-failure
User=<your_username>

[Install]
WantedBy=multi-user.target
```
</details>

<details>
<summary><code>transcriber-worker.service</code></summary>

```ini
[Unit]
Description=Transcriber Worker Service
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/<your_username>/transcriber-app/app/worker.py
Restart=on-failure
User=<your_username>

[Install]
WantedBy=multi-user.target
```
</details>

<details>
<summary><code>transcriber-web.service</code></summary>

```ini
[Unit]
Description=Transcriber Web Service (Flask)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/<your_username>/transcriber-app/app/web_server.py
Restart=on-failure
User=<your_username>
WorkingDirectory=/home/<your_username>/transcriber-app/app

[Install]
WantedBy=multi-user.target
```
</details>

### 8. Enable and Start Services

Once the service files are created, enable them to start on boot and then start them for the first time.

```bash
sudo systemctl daemon-reload
sudo systemctl enable transcriber-hw.service
sudo systemctl enable transcriber-worker.service
sudo systemctl enable transcriber-web.service

sudo systemctl start transcriber-hw.service
sudo systemctl start transcriber-worker.service
sudo systemctl start transcriber-web.service
```

Your appliance is now running! You can access the web interface by navigating to your Raspberry Pi's IP address in a web browser.
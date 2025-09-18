# Setup Guide

This guide details how to set up the Raspberry Pi from a fresh OS install to a fully functional transcription appliance using the automated setup script.

### 1. Initial Pi Setup

1.  Install Raspberry Pi OS (64-bit Lite recommended) on your microSD card.
2.  Enable SSH and configure your Wi-Fi credentials.
3.  Boot the Pi and connect to it via SSH.

### 2. Clone the Application Repository

Clone this repository to your Pi's home directory.

```bash
cd ~
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

*Note: Replace the URL with your actual repository URL.*

### 3. Run the Automated Setup Script

The `setup.sh` script automates all the necessary installation and configuration steps, including:
*   Installing system dependencies.
*   Downloading the required AI models.
*   Creating a dedicated service user.
*   Copying application files.
*   Configuring the device to act as a Wi-Fi Access Point (SSID: `TranscriberAP`).
*   Setting up and enabling `systemd` services to run on boot.

Run the script with `sudo`:
    ```bash
    sudo ./setup.sh
    ```
After the script completes, reboot the Pi.

Your appliance is now running! You can connect to its Wi-Fi network (`TranscriberAP`) and access the web interface by navigating to `http://192.168.4.1` in a web browser.

If you plug in a secondary USB Wi-Fi adapter, you can use the "Network Management" section of the web UI to connect the appliance to another Wi-Fi network for internet access.
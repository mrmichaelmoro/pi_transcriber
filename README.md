# Headless Offline Transcription Appliance v2.0

This project turns a Raspberry Pi into a headless, network-accessible appliance for recording, transcribing, and analyzing audio offline. Version 2.0 introduces a complete architectural overhaul for improved stability, responsiveness, and usability.

## v2.0 Features

*   **Web Interface**: A full web UI allows you to manage the appliance from any device on the same network. You can list, download, or delete transcripts and even upload your own audio files for processing.
*   **Background Processing**: A multi-process architecture using a job queue ensures that the device remains responsive. Audio recording and the web server are not blocked by intensive transcription or AI analysis tasks.
*   **Robust and Headless**: Designed to run automatically on boot without a monitor or keyboard. Physical controls (a switch and an LED) provide a simple interface for recording on the go.
*   **Fully Offline**: All processing, from transcription to AI-powered summarization, happens locally on the device. No internet connection is required for its core functionality.

## Project Structure

The project is organized into distinct components for clarity and maintainability.

```
.
├── app/                  # Core Python application logic
│   ├── transcriber.py    # Hardware script for recording
│   ├── worker.py         # Background processor for transcription/analysis
│   ├── web_server.py     # Flask backend API
│   └── requirements.txt  # Python dependencies
├── nginx/                # Nginx configuration
│   └── nginx.conf
├── web_ui/               # Static frontend files
│   └── index.html
├── README.md             # This file
├── hardware_guide.md     # Wiring instructions
└── setup_guide.md        # System installation and configuration guide
```
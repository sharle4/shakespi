#!/bin/bash
set -e

echo "Starting Shakespi installation on Raspberry Pi..."

# 1. Update and install system dependencies
echo "Installing system dependencies..."
sudo apt-update
sudo apt-get install -y python3-pip python3-venv git alsa-utils libportaudio2 libasound2-dev

# 2. Create Python virtual environment
echo "Setting up Python virtual environment..."
cd /home/pi/shakespi
python3 -m venv venv
source venv/bin/activate

# 3. Install Python requirements
echo "Installing Python packages..."
# We generate a temporary requirements file or install directly
pip install evdev sounddevice soundfile numpy pyyaml google-generativeai requests python-dotenv

# 4. Install Piper TTS binary
echo "Downloading Piper TTS..."
mkdir -p bin
cd bin
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
tar -xf piper_arm64.tar.gz
rm piper_arm64.tar.gz
# Add piper to path in the service file or link it to venv
ln -sf $(pwd)/piper/piper /home/pi/shakespi/venv/bin/piper
cd ..

# 5. Download Piper voices
echo "Downloading Piper voices..."
mkdir -p models
cd models
# French medium
wget -nc https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx
wget -nc https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx.json
# English medium
wget -nc https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget -nc https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
cd ..

# 6. Copy config example if not exists
if [ ! -f config/config.yaml ]; then
    cp config/config.example.yaml config/config.yaml
    echo "Created config.yaml. PLEASE EDIT THIS FILE to add your API keys."
fi

# 7. Add user to input and audio groups
echo "Adding pi user to input and audio groups..."
sudo usermod -a -G input pi
sudo usermod -a -G audio pi

echo "Installation script completed successfully!"
echo "Please follow INSTALL_PI.md for remaining steps."

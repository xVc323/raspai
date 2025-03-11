#!/bin/bash
# RaspAI Setup Script
# This script sets up the RaspAI voice assistant on a Raspberry Pi

set -e  # Exit on error

echo "============================================="
echo "RaspAI Voice Assistant Setup"
echo "============================================="

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This doesn't appear to be a Raspberry Pi."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

echo "Updating system packages..."
sudo apt update
sudo apt upgrade -y

echo "Installing required system packages..."
sudo apt install -y python3-pip python3-venv
sudo apt install -y python3-pyaudio portaudio19-dev
sudo apt install -y libespeak-dev libespeak1  # Required for pyttsx3

# Create a virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install wheel
pip install -r requirements.txt

# Set up .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo
    echo "Please edit the .env file to add your Gemini API key:"
    echo "nano .env"
fi

# Set up autostart (optional)
read -p "Do you want RaspAI to start automatically on boot? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Setting up autostart..."
    
    # Create systemd service file
    SERVICE_FILE="/etc/systemd/system/raspai.service"
    
    # Get current directory
    CURRENT_DIR=$(pwd)
    
    sudo bash -c "cat > $SERVICE_FILE << EOF
[Unit]
Description=RaspAI Voice Assistant
After=network.target sound.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python3 $CURRENT_DIR/raspai.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"
    
    # Enable and start the service
    sudo systemctl enable raspai.service
    echo "Service created and enabled. Will start on next boot."
    
    read -p "Do you want to start the service now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl start raspai.service
        echo "Service started. Check status with: sudo systemctl status raspai.service"
    fi
fi

echo
echo "============================================="
echo "Setup complete!"
echo "============================================="
echo
echo "To run RaspAI manually:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the assistant: python raspai.py"
echo 
echo "To use the advanced version: python raspai_advanced.py"
echo
echo "To control with a button: python button_control.py"
echo
echo "Enjoy your new voice assistant!" 
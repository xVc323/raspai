#!/bin/bash
# RaspAI Deployment Script
# This script deploys the RaspAI voice assistant to a Raspberry Pi

echo "============================================="
echo "RaspAI Voice Assistant Deployment"
echo "============================================="
echo

# Prompt for connection details instead of hardcoding them
read -p "Enter Raspberry Pi hostname or IP address: " PI_HOST
read -p "Enter the remote username (e.g., pi): " PI_USER
read -p "Enter the destination directory on Raspberry Pi: " PI_DIR

# Form the full SSH target
SSH_TARGET="${PI_USER}@${PI_HOST}"

# Ask about deploying legacy scripts
read -p "Do you want to include legacy standalone scripts? (y/n): " INCLUDE_LEGACY
if [[ $INCLUDE_LEGACY =~ ^[Yy]$ ]]; then
    LEGACY_FILES="raspai.py raspai_advanced.py passive_listener.py button_control.py"
    echo "Legacy scripts will be included."
else
    LEGACY_FILES=""
    echo "Only the integrated solution will be deployed."
fi

echo
echo "NOTE: If you use password authentication for SSH, you will be prompted"
echo "to enter your password multiple times during this process."
echo "For a smoother experience, consider setting up SSH key authentication."
echo

# Check SSH connection
echo "Testing SSH connection to ${SSH_TARGET}..."
ssh -q ${SSH_TARGET} "exit"
if [ $? -ne 0 ]; then
    echo "Error: Cannot connect to Raspberry Pi. Please check your connection."
    exit 1
fi
echo "SSH connection successful!"

# Create directory on Pi if it doesn't exist
echo "Creating project directory ${PI_DIR} on Raspberry Pi..."
ssh ${SSH_TARGET} "mkdir -p ${PI_DIR}"

# Transfer essential files
echo "Transferring essential files to Raspberry Pi..."
ESSENTIAL_FILES=".env .env.example README.md INTEGRATED_README.md requirements.txt setup.sh raspai_integrated.py test_components.py"

scp -r $ESSENTIAL_FILES ${SSH_TARGET}:${PI_DIR}/

# Transfer legacy files if requested
if [[ -n "$LEGACY_FILES" ]]; then
    echo "Transferring legacy files to Raspberry Pi..."
    scp -r $LEGACY_FILES ${SSH_TARGET}:${PI_DIR}/
fi

echo "Files transferred successfully!"

# Ask if user wants to run setup automatically
read -p "Do you want to run the setup script on your Raspberry Pi now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running setup script on Raspberry Pi..."
    ssh ${SSH_TARGET} "cd ${PI_DIR} && chmod +x setup.sh && ./setup.sh"
else
    echo "To set up your Raspberry Pi later, run:"
    echo "  ssh ${SSH_TARGET}"
    echo "  cd ${PI_DIR}"
    echo "  chmod +x setup.sh"
    echo "  ./setup.sh"
fi

echo
echo "============================================="
echo "Deployment complete!"
echo "============================================="
echo
echo "To run the integrated voice assistant:"
echo "  ssh ${SSH_TARGET}"
echo "  cd ${PI_DIR}"
echo "  python3 raspai_integrated.py"
echo
echo "If you frequently deploy to your Raspberry Pi, consider setting up"
echo "SSH keys for password-less authentication:"
echo
echo "  ssh-keygen -t rsa -b 4096"
echo "  ssh-copy-id ${SSH_TARGET}" 
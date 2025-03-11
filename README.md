# RaspAI - Voice Assistant for Raspberry Pi

![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)

A powerful voice assistant powered by Google's Gemini AI, designed to run on a Raspberry Pi.

## ✨ Latest Update: Integrated Voice Assistant

We've combined the main voice assistant and passive listener into a single integrated script that offers both features simultaneously. This is now the recommended way to use RaspAI.

**Key Features:**
- 🎙️ Voice assistant activated by "Hey Raspberry" wake word
- 🔊 Optional passive listener that makes funny comments about what it hears
- 🔘 Toggle the passive listener on/off with a hardware button or keyboard shortcut
- 💡 LED indicator shows when passive listener is active

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi 3B or better (only the 3B version has been tested)
- USB microphone
- Speaker (via 3.5mm jack or HDMI)
- Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/xvc323/raspai.git
   cd raspai
   ```

2. Set up your `.env` file with your Google Gemini API key:
   ```bash
   cp .env.example .env
   # Edit .env with your text editor and add your API key
   ```

3. Deploy to your Raspberry Pi:
   ```bash
   ./deploy.sh
   ```

4. Run the integrated assistant:
   ```bash
   python3 raspai_integrated.py
   ```

For detailed instructions, see [INTEGRATED_README.md](INTEGRATED_README.md)

## 📂 Project Files

### Core Files
- `raspai_integrated.py` - **[RECOMMENDED]** The main script with both voice assistant and passive listener features
- `test_components.py` - Test your microphone, speaker, and other components
- `deploy.sh` - Deploy files to your Raspberry Pi
- `setup.sh` - Set up dependencies on your Raspberry Pi

### Hardware Requirements
- Raspberry Pi 3B or better
- USB microphone
- Speaker (via 3.5mm jack or HDMI)
- Optional: Push button on GPIO pin 17
- Optional: LED on GPIO pin 27

## 📚 Documentation
- [INTEGRATED_README.md](INTEGRATED_README.md) - Detailed guide for the integrated solution

## 🧰 Legacy Scripts

Standalone versions of the assistant and passive listener are still available:
- `raspai.py` - Basic voice assistant
- `raspai_advanced.py` - Advanced voice assistant
- `passive_listener.py` - Standalone passive listener

These are provided for compatibility but are no longer actively developed.

## 📷 GPIO Connection Diagram

```
Raspberry Pi GPIO    Button/LED Connection
----------------|-------------------------
GPIO 17 (Pin 11) --- Push Button --- GND
GPIO 27 (Pin 13) --- 330Ω Resistor --- LED Anode --- LED Cathode --- GND
```

## 📋 Dependencies

- google-generativeai - Google's Gemini AI API
- SpeechRecognition - For speech recognition
- PyAudio - For audio processing
- pyttsx3 - For text-to-speech
- python-dotenv - For environment variable management
- RPi.GPIO - For GPIO control

## 📝 License

This project is free to use for personal projects. 
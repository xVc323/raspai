# RaspAI Integrated Voice Assistant

The RaspAI Integrated Voice Assistant combines the main voice assistant and passive listener features into a single script, allowing you to switch between modes with a physical button press or keyboard shortcuts.

## Features

- **Voice Assistant Mode**: Always active, responds to "Hey Raspberry" wake word
- **Passive Listener Mode**: Can be toggled on/off with a button press or keyboard shortcut
- **Both Modes Can Run Simultaneously**: Unlike previous implementations, these features can coexist
- **LED Status Indicator**: Shows whether passive listener is active
- **Hardware Control**: Uses GPIO pins for button and LED interaction
- **Software Control**: Keyboard shortcuts for systems without GPIO access

## Hardware Requirements

- Raspberry Pi 3B or better
- USB microphone (the 3.5mm audio jack does not support audio input)
- Optional hardware components:
  - Push button connected to GPIO pin (default: GPIO 17)
  - LED connected to GPIO pin (default: GPIO 27)
  - Resistors:
    - 10K ohm pull-up resistor for button
    - 330 ohm current-limiting resistor for LED

## GPIO Connection Diagram

```
Raspberry Pi GPIO    Button/LED Connection
----------------|-------------------------
GPIO 17 (Pin 11) --- Push Button --- GND
GPIO 27 (Pin 13) --- 330Ω Resistor --- LED Anode --- LED Cathode --- GND
```

## Installation

1. Deploy the files to your Raspberry Pi with the deployment script:
   ```
   ./deploy.sh
   ```

2. Install required dependencies:
   ```
   pip3 install -r requirements.txt
   ```

3. Set up your `.env` file with your Google Gemini API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage

Run the integrated assistant:

```bash
python3 raspai_integrated.py
```

### Control Methods

#### Hardware Button Control
If you have a button connected to GPIO, press it to toggle the passive listener on/off.

#### Keyboard Control
If hardware buttons aren't available or if you're testing on a non-Raspberry Pi system, you can use keyboard shortcuts:
- Press `t` to toggle the passive listener on/off
- Press `q` to quit the application

### Command Line Options

- `--button_pin PIN` - GPIO pin for the toggle button (default: 17)
- `--led_pin PIN` - GPIO pin for the status LED (default: 27)
- `--interval MINUTES` - Minutes between passive listener commentaries (default: 5)
- `--harshness LEVEL` - Harshness level for comments (1-5, default: 3)

Examples:

```bash
# Use different GPIO pins
python3 raspai_integrated.py --button_pin 23 --led_pin 24

# Change passive listener settings
python3 raspai_integrated.py --interval 10 --harshness 4

# Combine options
python3 raspai_integrated.py --button_pin 23 --led_pin 24 --interval 10 --harshness 4
```

## How It Works

### Voice Assistant
- Always listens for the wake word "Hey Raspberry"
- When the wake word is detected, it plays a sound and prompts for your query
- Your query is sent to Google's Gemini AI for processing
- The response is spoken using text-to-speech

### Passive Listener
- Can be toggled on/off with a button press or 't' key (LED turns on when active)
- When active, it periodically records audio (default: every 5 minutes)
- If meaningful sound is detected during recording, it transcribes the audio
- It sends the transcription to Gemini AI requesting a funny commentary
- The AI-generated comment is spoken aloud using text-to-speech
- Waits for the configured interval before recording again

## Running in the Background

To run the integrated assistant in the background, even after you close your SSH session:

```bash
nohup python3 raspai_integrated.py > raspai.log 2>&1 &
```

To stop it later:

```bash
ps aux | grep raspai_integrated.py
kill [PID]  # Replace [PID] with the process ID from the previous command
```

## Testing Without Raspberry Pi Hardware

The integrated assistant can be tested on a regular computer (macOS, Linux, etc.) without GPIO capabilities. When run on a system without GPIO access, it will automatically fall back to keyboard control mode:

1. Install the dependencies on your computer (you may need to modify some for your platform)
2. Run the script: `python3 raspai_integrated.py`
3. The script will detect that GPIO is not available and enable keyboard controls
4. Use the 't' key to toggle the passive listener on/off

Note that testing on a non-Raspberry Pi system may require additional configuration for audio input/output.

## Troubleshooting

### Microphone Issues
- Make sure your USB microphone is connected
- Run `arecord -l` to list audio capture devices
- Adjust the ALSA settings if needed: `sudo nano /etc/asound.conf`

### GPIO Issues
- Ensure your button and LED are connected to the correct GPIO pins
- Check resistor values (10K ohm for button pull-up, 330 ohm for LED)
- Test with simple GPIO test scripts to verify connections

### Audio Output Issues
- Run `aplay -l` to list playback devices
- Adjust the output volume: `alsamixer`
- Check audio device settings: `sudo nano /etc/asound.conf`

## Customization

### Changing the Wake Word
Edit the `WAKE_WORD` constant in the script to change the wake word:

```python
WAKE_WORD = "your custom wake word here"
```

### Adjusting Sound Detection Sensitivity
If the passive listener is too sensitive or not sensitive enough, adjust the `SOUND_THRESHOLD` constant:

```python
SOUND_THRESHOLD = 2000  # Higher value = less sensitive, lower value = more sensitive
```

### Voice Customization
The script uses a random voice for passive listener commentary. You can modify the voice selection logic in the `PassiveListener.run_commentary_cycle()` method. 
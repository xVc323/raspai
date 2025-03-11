#!/usr/bin/env python3
"""
RaspAI Integrated Voice Assistant

This script combines the main voice assistant with the optional passive listener feature.
- The voice assistant responds to "Hey Raspberry" wake word
- The passive listener can be toggled on/off with a GPIO button press
- Both features can work simultaneously when passive listener is enabled

Usage:
    python3 raspai_integrated.py [--button_pin PIN] [--led_pin PIN] [--harshness LEVEL] [--interval MINUTES]

Requirements:
    See requirements.txt
"""

import os
import sys
import time
import json
import wave
import signal
import argparse
import datetime
import threading
import random
import queue
import numpy as np
import pyaudio
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
from dotenv import load_dotenv
import RPi.GPIO as GPIO

# Load environment variables from .env file
load_dotenv()

# Configuration
WAKE_WORD = "hey raspberry"  # Wake word to trigger the assistant
AUDIO_TIMEOUT = 5  # Seconds to listen for after wake word
SAMPLE_RATE = 16000  # Audio sample rate
CHANNELS = 1  # Mono audio
CHUNK = 1024  # Audio chunk size

# Passive listener configuration
DEFAULT_INTERVAL = 5  # Minutes between commentaries
DEFAULT_HARSHNESS = 3  # On a scale of 1-5 (1=mild, 5=brutal)
SOUND_THRESHOLD = 2000  # Threshold for sound detection (adjust as needed)
MIN_SOUND_DURATION = 2  # Minimum seconds of sound to trigger processing
TEMP_AUDIO_FILE = "temp_recording.wav"

# GPIO configuration
DEFAULT_BUTTON_PIN = 17  # GPIO pin for passive listener toggle button
DEFAULT_LED_PIN = 27  # GPIO pin for passive listener status LED

# Audio device lock to prevent simultaneous recording
audio_lock = threading.Lock()

# Google Gemini AI configuration
try:
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    # Configure the Gemini API
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    
except Exception as e:
    print(f"Error configuring Gemini AI: {e}")
    exit(1)

class AudioFeedback:
    """Class to handle audio feedback like beeps and notification sounds."""
    
    def __init__(self):
        """Initialize the audio feedback system."""
        self.pyaudio_instance = pyaudio.PyAudio()
    
    def play_tone(self, frequency, duration, volume=0.5):
        """Play a simple tone with the given frequency and duration."""
        # Generate a sine wave for the tone
        sample_rate = 44100  # Standard audio sample rate
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = np.sin(frequency * 2 * np.pi * t) * volume
        
        # Convert to the required format
        audio_data = (tone * 32767).astype(np.int16).tobytes()
        
        # Play the tone
        stream = self.pyaudio_instance.open(
            format=self.pyaudio_instance.get_format_from_width(2),
            channels=1,
            rate=sample_rate,
            output=True
        )
        stream.write(audio_data)
        stream.stop_stream()
        stream.close()
    
    def wake_sound(self):
        """Play a sound to indicate wake word detection."""
        # Play ascending tones
        self.play_tone(440, 0.1)  # A4
        self.play_tone(523, 0.1)  # C5
        self.play_tone(659, 0.1)  # E5
    
    def listening_sound(self):
        """Play a sound to indicate the assistant is listening."""
        self.play_tone(587, 0.2)  # D5
    
    def processing_sound(self):
        """Play a sound to indicate the assistant is processing."""
        self.play_tone(440, 0.1)  # A4
    
    def response_sound(self):
        """Play a sound to indicate the assistant is about to respond."""
        # Play descending tones
        self.play_tone(659, 0.1)  # E5
        self.play_tone(523, 0.1)  # C5
        self.play_tone(440, 0.1)  # A4
    
    def passive_on_sound(self):
        """Play a sound to indicate passive listener is turned on."""
        # Play two ascending tones
        self.play_tone(392, 0.1)  # G4
        self.play_tone(523, 0.1)  # C5
    
    def passive_off_sound(self):
        """Play a sound to indicate passive listener is turned off."""
        # Play two descending tones
        self.play_tone(523, 0.1)  # C5
        self.play_tone(392, 0.1)  # G4
    
    def comment_coming_sound(self):
        """Play a sound to indicate a passive listener comment is coming."""
        # Play a special sequence for comments
        self.play_tone(392, 0.1)  # G4
        self.play_tone(440, 0.1)  # A4
        self.play_tone(494, 0.1)  # B4
    
    def error_sound(self):
        """Play a sound to indicate an error."""
        self.play_tone(220, 0.3)  # A3 (low tone)
    
    def cleanup(self):
        """Clean up resources."""
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

class SharedTTS:
    """Shared text-to-speech functionality to avoid conflicts between threads."""
    
    def __init__(self):
        """Initialize the shared TTS engine."""
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)  # Speed of speech
        self.tts_engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.running = True
        
        # Start the TTS worker thread
        self.tts_thread = threading.Thread(target=self._tts_worker)
        self.tts_thread.daemon = True
        self.tts_thread.start()
    
    def _tts_worker(self):
        """Worker thread to process TTS requests."""
        while self.running:
            try:
                text, voice_id = self.queue.get(timeout=0.5)
                if text:
                    with self.lock:
                        if voice_id:
                            self.tts_engine.setProperty('voice', voice_id)
                        self.tts_engine.say(text)
                        self.tts_engine.runAndWait()
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS error: {e}")
    
    def speak(self, text, voice_id=None):
        """Add text to the TTS queue.
        
        Args:
            text: Text to speak
            voice_id: Optional voice ID to use
        """
        if text:
            self.queue.put((text, voice_id))
    
    def cleanup(self):
        """Clean up resources."""
        self.running = False
        if self.tts_thread.is_alive():
            self.tts_thread.join(timeout=2)

class VoiceAssistant:
    """Main voice assistant class that responds to wake word."""
    
    def __init__(self, shared_tts):
        """Initialize the voice assistant.
        
        Args:
            shared_tts: SharedTTS instance for text-to-speech
        """
        self.recognizer = sr.Recognizer()
        
        # Use shared TTS
        self.shared_tts = shared_tts
        
        # Initialize the microphone
        self.microphone = sr.Microphone()
        
        # Initialize audio feedback
        self.audio_feedback = AudioFeedback()
        
        # Calibrate recognizer for ambient noise
        with audio_lock:
            with self.microphone as source:
                print("Calibrating for ambient noise... Please wait.")
                self.recognizer.adjust_for_ambient_noise(source, duration=3)
                print("Calibration complete. Ready to listen!")
        
        # Flag to control main loop
        self.running = True
    
    def listen_for_wake_word(self):
        """Listen for the wake word and return True if heard."""
        print(f"Listening for wake word: '{WAKE_WORD}'")
        
        with audio_lock:
            with self.microphone as source:
                try:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=3)
                    text = self.recognizer.recognize_google(audio).lower()
                    print(f"Heard: {text}")
                    
                    if WAKE_WORD.lower() in text:
                        print("Wake word detected!")
                        self.audio_feedback.wake_sound()
                        self.shared_tts.speak("How can I help you?")
                        return True
                except sr.WaitTimeoutError:
                    return False
                except sr.UnknownValueError:
                    return False
                except Exception as e:
                    print(f"Error in wake word detection: {e}")
                    return False
        
        return False
    
    def listen_for_query(self):
        """Listen for user query after wake word detection."""
        print("Listening for your query...")
        self.audio_feedback.listening_sound()
        
        with audio_lock:
            with self.microphone as source:
                try:
                    audio = self.recognizer.listen(source, timeout=AUDIO_TIMEOUT, phrase_time_limit=10)
                    text = self.recognizer.recognize_google(audio)
                    print(f"Query: {text}")
                    return text
                except sr.UnknownValueError:
                    print("Sorry, I didn't understand that.")
                    self.shared_tts.speak("Sorry, I didn't understand that.")
                    return None
                except sr.RequestError:
                    print("Sorry, I couldn't request results. Check your network connection.")
                    self.shared_tts.speak("Sorry, I couldn't process that. Check your network connection.")
                    return None
                except Exception as e:
                    print(f"Error in query: {e}")
                    self.audio_feedback.error_sound()
                    self.shared_tts.speak("Sorry, something went wrong.")
                    return None
    
    def process_with_gemini(self, query):
        """Send the query to Gemini AI and get a response."""
        if not query:
            return "I didn't catch that. Can you try again?"
        
        try:
            # Generate content using Gemini AI
            response = model.generate_content(query)
            response_text = response.text
            print(f"Gemini response: {response_text}")
            return response_text
        except Exception as e:
            print(f"Error processing with Gemini: {e}")
            return "Sorry, I encountered an error processing your request."
    
    def run(self):
        """Main loop for the voice assistant."""
        print("RaspAI Voice Assistant started!")
        print(f"Say '{WAKE_WORD}' to start...")
        
        while self.running:
            if self.listen_for_wake_word():
                query = self.listen_for_query()
                if query:
                    response = self.process_with_gemini(query)
                    self.audio_feedback.response_sound()
                    self.shared_tts.speak(response)
            
            # Small delay to reduce CPU usage
            time.sleep(0.1)
    
    def cleanup(self):
        """Clean up resources before exit."""
        self.running = False
        if self.audio_feedback:
            self.audio_feedback.cleanup()

class PassiveListener:
    """Passive listener that periodically makes comments about what it hears."""
    
    def __init__(self, shared_tts, interval=DEFAULT_INTERVAL, harshness=DEFAULT_HARSHNESS):
        """Initialize the passive listener.
        
        Args:
            shared_tts: SharedTTS instance for text-to-speech
            interval: Minutes between commentaries
            harshness: Level of harshness for comments (1-5)
        """
        self.interval = interval * 60  # Convert to seconds
        self.harshness = harshness
        
        # Use shared TTS
        self.shared_tts = shared_tts
        
        # Initialize audio feedback
        self.audio_feedback = AudioFeedback()
        
        # Initialize PyAudio for recording
        self.pyaudio = pyaudio.PyAudio()
        
        # Flags to control operations
        self.running = False  # Start disabled by default
        self.thread = None
        self.stop_event = threading.Event()
        
        # For sound detection
        self.current_state = 0  # 0 = silence, 1 = sound
        self.sound_start_time = 0
        self.total_sound_duration = 0
        self.any_sound_detected = False
        
        # For transcription
        self.recognizer = sr.Recognizer()
        
        print(f"Passive listener initialized with {interval} minute intervals and harshness level {harshness}")
    
    def _calculate_audio_energy(self, data):
        """Calculate the energy (loudness) of audio data."""
        data_np = np.frombuffer(data, dtype=np.int16)
        return np.sqrt(np.mean(np.square(data_np)))
    
    def _detect_sound_activity(self, audio_data):
        """Detect sound activity in the audio data."""
        energy = self._calculate_audio_energy(audio_data)
        
        if energy > SOUND_THRESHOLD:
            if self.current_state == 0:  # Was silence, now sound
                self.current_state = 1
                self.sound_start_time = time.time()
            else:
                # Continue in sound state, accumulate duration
                sound_duration = time.time() - self.sound_start_time
                if sound_duration >= MIN_SOUND_DURATION and not self.any_sound_detected:
                    print(f"Sound detected! Energy: {energy:.2f}")
                    self.any_sound_detected = True
        else:
            if self.current_state == 1:  # Was sound, now silence
                # Transition from sound to silence
                sound_duration = time.time() - self.sound_start_time
                self.total_sound_duration += sound_duration
                self.current_state = 0
    
    def record_audio(self, duration):
        """Record audio for a specified duration while detecting sound activity.
        
        Args:
            duration: Recording duration in seconds
            
        Returns:
            bool: Whether any meaningful sound was detected
        """
        if not self.running or self.stop_event.is_set():
            return False
            
        print(f"[Passive] Recording for {duration} seconds...")
        
        # Reset sound detection state
        self.current_state = 0
        self.total_sound_duration = 0
        self.any_sound_detected = False
        
        with audio_lock:
            try:
                # Set up recording stream
                stream = self.pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                
                frames = []
                for _ in range(0, int(SAMPLE_RATE / CHUNK * duration)):
                    if self.stop_event.is_set():
                        break
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                    self._detect_sound_activity(data)
                
                # Close stream
                stream.stop_stream()
                stream.close()
                
                # Save audio to a temporary file if we detected sound
                if self.any_sound_detected and len(frames) > 0:
                    wf = wave.open(TEMP_AUDIO_FILE, 'wb')
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(self.pyaudio.get_sample_format_from_width(2))
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(b''.join(frames))
                    wf.close()
            except Exception as e:
                print(f"[Passive] Recording error: {e}")
                return False
        
        print(f"[Passive] Recording complete. Sound detected: {self.any_sound_detected}")
        print(f"[Passive] Total sound duration: {self.total_sound_duration:.2f} seconds")
        
        return self.any_sound_detected
    
    def transcribe_audio(self):
        """Attempt to transcribe the recorded audio."""
        try:
            with sr.AudioFile(TEMP_AUDIO_FILE) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                return text
        except Exception as e:
            print(f"[Passive] Transcription error: {e}")
            return ""
    
    def get_gemini_commentary(self, transcription=""):
        """Get a funny, harsh commentary from Gemini AI."""
        harshness_descriptions = {
            1: "slightly sarcastic but gentle",
            2: "sarcastic and a bit critical",
            3: "mean and sarcastic",
            4: "very harsh and critical",
            5: "brutally honest and mercilessly harsh"
        }
        
        harshness_desc = harshness_descriptions.get(self.harshness, "harsh")
        
        prompt = f"""You are a {harshness_desc} commentator who overheard some audio.
        
        Make a brief, funny, {harshness_desc} comment (max 50 words) about what you heard or the lack of anything interesting.
        
        Be creative and make jokes about the content, quality, or lack of interesting material.
        
        {"Here's what you heard: " + transcription if transcription else "You heard nothing interesting at all."}
        """
        
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"[Passive] Error getting commentary from Gemini: {e}")
            return "I was going to say something mean, but even I'm not interested in what I just heard."
    
    def run_commentary_cycle(self):
        """Run one full cycle of recording and commentary."""
        if not self.running or self.stop_event.is_set():
            return
            
        # Record audio for a short duration
        recording_duration = min(30, self.interval // 4)  # Keep recordings shorter
        sound_detected = self.record_audio(recording_duration)
        
        if sound_detected and not self.stop_event.is_set():
            # Try to transcribe the audio
            transcription = self.transcribe_audio()
            
            # Get and speak commentary
            commentary = self.get_gemini_commentary(transcription)
            
            if not self.stop_event.is_set():
                print(f"[Passive] Commentary: {commentary}")
                self.audio_feedback.comment_coming_sound()
                
                # Use random voice if available
                voice_id = None
                try:
                    voices = self.shared_tts.tts_engine.getProperty('voices')
                    if voices and len(voices) > 1:
                        voice_id = random.choice(voices).id
                except:
                    pass
                
                self.shared_tts.speak(commentary, voice_id)
        else:
            print("[Passive] No meaningful sound detected, skipping commentary")
    
    def _listener_loop(self):
        """Main loop for the passive listener thread."""
        print("[Passive] Passive listener thread started")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Run a full commentary cycle
                self.run_commentary_cycle()
                
                # Wait until next interval, checking for stop signal periodically
                wait_time = self.interval
                wait_start = time.time()
                while time.time() - wait_start < wait_time and not self.stop_event.is_set():
                    remaining = wait_time - (time.time() - wait_start)
                    if remaining > 0:
                        print(f"[Passive] Next commentary in {int(remaining)} seconds...")
                    time.sleep(min(10, remaining))  # Check stop signal every 10 seconds max
            
            except Exception as e:
                print(f"[Passive] Error in passive listener loop: {e}")
                time.sleep(5)  # Wait a bit before retrying
                
        print("[Passive] Passive listener thread stopped")
    
    def start(self):
        """Start the passive listener."""
        if not self.running:
            self.running = True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._listener_loop)
            self.thread.daemon = True
            self.thread.start()
            print("[Passive] Passive listener started")
            self.audio_feedback.passive_on_sound()
            return True
        return False
    
    def stop(self):
        """Stop the passive listener."""
        if self.running:
            self.running = False
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=2)
                self.thread = None
            print("[Passive] Passive listener stopped")
            self.audio_feedback.passive_off_sound()
            return True
        return False
    
    def toggle(self):
        """Toggle the passive listener on/off."""
        if self.running:
            return self.stop()
        else:
            return self.start()
    
    def cleanup(self):
        """Clean up resources before exit."""
        self.stop()
        if self.audio_feedback:
            self.audio_feedback.cleanup()
        
        if self.pyaudio:
            self.pyaudio.terminate()
        
        # Remove temporary audio file
        if os.path.exists(TEMP_AUDIO_FILE):
            try:
                os.remove(TEMP_AUDIO_FILE)
            except:
                pass

class IntegratedAssistant:
    """Main class that integrates voice assistant and passive listener features."""
    
    def __init__(self, button_pin=DEFAULT_BUTTON_PIN, led_pin=DEFAULT_LED_PIN, 
                 interval=DEFAULT_INTERVAL, harshness=DEFAULT_HARSHNESS):
        """Initialize the integrated assistant.
        
        Args:
            button_pin: GPIO pin for passive listener toggle button
            led_pin: GPIO pin for passive listener status LED
            interval: Minutes between passive listener commentaries
            harshness: Level of harshness for comments (1-5)
        """
        # Initialize GPIO
        self.button_pin = button_pin
        self.led_pin = led_pin
        self.gpio_available = self.setup_gpio()
        
        # Initialize shared TTS
        self.shared_tts = SharedTTS()
        
        # Initialize voice assistant
        self.voice_assistant = VoiceAssistant(self.shared_tts)
        
        # Initialize passive listener
        self.passive_listener = PassiveListener(
            self.shared_tts,
            interval=interval,
            harshness=harshness
        )
        
        # Register signal handlers for clean exit
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        # Start the voice assistant in a separate thread
        self.assistant_thread = threading.Thread(target=self.voice_assistant.run)
        self.assistant_thread.daemon = True
        
        # Start a keyboard listener thread if GPIO is not available
        if not self.gpio_available:
            self.keyboard_thread = threading.Thread(target=self._keyboard_listener)
            self.keyboard_thread.daemon = True
    
    def setup_gpio(self):
        """Set up GPIO for button and LED.
        
        Returns:
            bool: Whether GPIO setup was successful
        """
        try:
            GPIO.setmode(GPIO.BCM)
            
            # Set up button with pull-up resistor
            GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Set up LED
            if self.led_pin:
                GPIO.setup(self.led_pin, GPIO.OUT)
                GPIO.output(self.led_pin, GPIO.LOW)
                
            # Add button event detection
            GPIO.add_event_detect(
                self.button_pin, 
                GPIO.FALLING, 
                callback=self.button_callback, 
                bouncetime=500
            )
            
            print(f"GPIO initialized. Press button on GPIO {self.button_pin} to toggle passive listener.")
            return True
            
        except Exception as e:
            print(f"Warning: Failed to initialize GPIO: {e}")
            print("Button control will not be available.")
            print("Using keyboard alternative: Press 't' to toggle passive listener.")
            return False
    
    def _keyboard_listener(self):
        """Listen for keyboard input to toggle passive listener."""
        print("Keyboard control active. Press 't' to toggle passive listener.")
        
        try:
            import termios
            import tty
            import sys
            
            def getch():
                """Get a single character from stdin."""
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    ch = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                return ch
            
            while True:
                char = getch()
                if char.lower() == 't':
                    print("\nToggle key pressed")
                    self.toggle_passive_listener()
                elif char.lower() == 'q':
                    print("\nQuitting...")
                    self.cleanup()
                    sys.exit(0)
        
        except Exception as e:
            print(f"Keyboard control error: {e}")
            print("Keyboard control disabled. Use Ctrl+C to exit.")
    
    def button_callback(self, channel):
        """Callback function for button press."""
        print("Button pressed - toggling passive listener")
        self.toggle_passive_listener()
    
    def toggle_passive_listener(self):
        """Toggle the passive listener on/off."""
        result = self.passive_listener.toggle()
        
        # Update LED status
        if self.gpio_available and self.led_pin:
            try:
                GPIO.output(self.led_pin, GPIO.HIGH if self.passive_listener.running else GPIO.LOW)
            except:
                pass
                
        status = "ON" if self.passive_listener.running else "OFF"
        print(f"Passive listener is now {status}")
        return result
    
    def run(self):
        """Run the integrated assistant."""
        print("\n" + "=" * 70)
        print("RaspAI Integrated Voice Assistant")
        print("=" * 70)
        print(f"• Say '{WAKE_WORD}' to activate the voice assistant")
        
        if self.gpio_available:
            print(f"• Press the button on GPIO {self.button_pin} to toggle passive listener")
            if self.led_pin:
                print(f"• LED on GPIO {self.led_pin} indicates passive listener status")
        else:
            print("• Press 't' key to toggle passive listener")
            print("• Press 'q' key to quit")
            
        print("• Press Ctrl+C to exit")
        print("=" * 70 + "\n")
        
        # Start the voice assistant thread
        self.assistant_thread.start()
        
        # Start keyboard listener if GPIO not available
        if not self.gpio_available:
            self.keyboard_thread.start()
        
        try:
            # Main thread just keeps running to handle signals properly
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            self.cleanup()
    
    def handle_signal(self, signum, frame):
        """Handle signals for clean exit."""
        print("\nReceived signal to exit...")
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Clean up resources before exit."""
        print("Cleaning up...")
        
        # Clean up passive listener
        if self.passive_listener:
            self.passive_listener.cleanup()
        
        # Clean up voice assistant
        if self.voice_assistant:
            self.voice_assistant.running = False
        
        # Clean up shared TTS
        if self.shared_tts:
            self.shared_tts.cleanup()
        
        # Clean up GPIO
        if self.gpio_available:
            try:
                GPIO.cleanup()
            except:
                pass

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="RaspAI Integrated Voice Assistant")
    parser.add_argument("--button_pin", type=int, default=DEFAULT_BUTTON_PIN,
                        help=f"GPIO pin for passive listener toggle button (default: {DEFAULT_BUTTON_PIN})")
    parser.add_argument("--led_pin", type=int, default=DEFAULT_LED_PIN,
                        help=f"GPIO pin for passive listener status LED (default: {DEFAULT_LED_PIN})")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"Minutes between passive listener commentaries (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--harshness", type=int, choices=range(1, 6), default=DEFAULT_HARSHNESS,
                        help=f"Harshness level 1-5 for passive listener (default: {DEFAULT_HARSHNESS})")
    return parser.parse_args()

def main():
    """Main function to start the integrated assistant."""
    args = parse_arguments()
    
    try:
        assistant = IntegratedAssistant(
            button_pin=args.button_pin,
            led_pin=args.led_pin,
            interval=args.interval,
            harshness=args.harshness
        )
        assistant.run()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main() 
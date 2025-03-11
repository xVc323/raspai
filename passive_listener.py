#!/usr/bin/env python3
"""
RaspAI Passive Listener

This script runs in the background, periodically recording audio and
sending it to Gemini AI for funny, harsh comments about what it heard.

IMPORTANT: This is an optional feature that is OFF by default and should 
not be run at the same time as the main voice assistant (raspai.py).

Features:
- Sound activity detection (only processes when actual sound is detected)
- Configurable recording interval
- Configurable harshness level
- Audio feedback with TTS for Gemini's comments

Usage:
    python3 passive_listener.py [--interval MINUTES] [--harshness LEVEL]
"""

import os
import sys
import time
import json
import wave
import argparse
import datetime
import threading
import random
import numpy as np
import pyaudio
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Default configuration
DEFAULT_INTERVAL = 5  # Minutes between commentaries
DEFAULT_HARSHNESS = 3  # On a scale of 1-5 (1=mild, 5=brutal)
SOUND_THRESHOLD = 2000  # Threshold for sound detection (adjust as needed)
MIN_SOUND_DURATION = 2  # Minimum seconds of sound to trigger processing
SAMPLE_RATE = 16000  # Audio sample rate
CHANNELS = 1  # Mono audio
CHUNK = 1024  # Audio chunk size
TEMP_AUDIO_FILE = "temp_recording.wav"

# Audio detection states
STATE_SILENCE = 0
STATE_SOUND = 1

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
    
    def start_recording_sound(self):
        """Play a sound to indicate recording is starting."""
        self.play_tone(523, 0.1)  # C5
        self.play_tone(659, 0.1)  # E5
    
    def stop_recording_sound(self):
        """Play a sound to indicate recording has stopped."""
        self.play_tone(659, 0.1)  # E5
        self.play_tone(523, 0.1)  # C5
    
    def comment_coming_sound(self):
        """Play a sound to indicate a comment is coming."""
        self.play_tone(440, 0.1)  # A4
        self.play_tone(523, 0.1)  # C5
        self.play_tone(659, 0.1)  # E5
    
    def cleanup(self):
        """Clean up resources."""
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

class PassiveListener:
    """Main class for the passive listener functionality."""
    
    def __init__(self, interval=DEFAULT_INTERVAL, harshness=DEFAULT_HARSHNESS):
        """Initialize the passive listener.
        
        Args:
            interval: Minutes between commentaries
            harshness: Level of harshness for comments (1-5)
        """
        self.interval = interval * 60  # Convert to seconds
        self.harshness = harshness
        
        # Initialize text-to-speech engine
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)  # Speed of speech
        self.tts_engine.setProperty('volume', 0.9)  # Volume
        
        # Initialize audio feedback
        self.audio_feedback = AudioFeedback()
        
        # Initialize PyAudio for recording
        self.pyaudio = pyaudio.PyAudio()
        
        # Flag to control main loop
        self.running = True
        
        # Keep track of sound detection
        self.current_state = STATE_SILENCE
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
            if self.current_state == STATE_SILENCE:
                self.current_state = STATE_SOUND
                self.sound_start_time = time.time()
            else:
                # Continue in sound state, accumulate duration
                sound_duration = time.time() - self.sound_start_time
                if sound_duration >= MIN_SOUND_DURATION and not self.any_sound_detected:
                    print(f"Sound detected! Energy: {energy:.2f}")
                    self.any_sound_detected = True
        else:
            if self.current_state == STATE_SOUND:
                # Transition from sound to silence
                sound_duration = time.time() - self.sound_start_time
                self.total_sound_duration += sound_duration
                self.current_state = STATE_SILENCE
    
    def record_audio(self, duration):
        """Record audio for a specified duration while detecting sound activity.
        
        Args:
            duration: Recording duration in seconds
            
        Returns:
            bool: Whether any meaningful sound was detected
        """
        print(f"Recording for {duration} seconds...")
        self.audio_feedback.start_recording_sound()
        
        # Reset sound detection state
        self.current_state = STATE_SILENCE
        self.total_sound_duration = 0
        self.any_sound_detected = False
        
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
            data = stream.read(CHUNK)
            frames.append(data)
            self._detect_sound_activity(data)
        
        # Close stream
        stream.stop_stream()
        stream.close()
        
        # Save audio to a temporary file
        wf = wave.open(TEMP_AUDIO_FILE, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.pyaudio.get_sample_format_from_width(2))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        self.audio_feedback.stop_recording_sound()
        
        print(f"Recording complete. Sound detected: {self.any_sound_detected}")
        print(f"Total sound duration: {self.total_sound_duration:.2f} seconds")
        
        return self.any_sound_detected
    
    def transcribe_audio(self):
        """Attempt to transcribe the recorded audio.
        
        Returns:
            str: Transcribed text or empty string if failed
        """
        try:
            with sr.AudioFile(TEMP_AUDIO_FILE) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                return text
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def get_gemini_commentary(self, transcription=""):
        """Get a funny, harsh commentary from Gemini AI.
        
        Args:
            transcription: Transcribed audio text
            
        Returns:
            str: Gemini's commentary
        """
        harshness_descriptions = {
            1: "slightly sarcastic but gentle",
            2: "sarcastic and a bit critical",
            3: "mean and sarcastic",
            4: "very harsh and critical",
            5: "brutally honest and mercilessly harsh"
        }
        
        harshness_desc = harshness_descriptions.get(self.harshness, "harsh")
        
        prompt = f"""You are a {harshness_desc} commentator who overheard some audio.
        
        Make a brief, funny, {harshness_desc} comment (50 words max) about what you heard or the lack of anything interesting.
        
        Be creative and make jokes about the content, quality, or lack of interesting material.
        
        {"Here's what you heard: " + transcription if transcription else "You heard nothing interesting at all."}
        """
        
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error getting commentary from Gemini: {e}")
            return "I was going to say something mean, but even I'm not interested in what I just heard."
    
    def speak(self, text):
        """Convert text to speech and play it.
        
        Args:
            text: Text to speak
        """
        if not text:
            return
        
        print(f"Commentary: {text}")
        self.audio_feedback.comment_coming_sound()
        time.sleep(0.3)  # Short delay before speaking
        
        # Randomly select a voice for variety
        voices = self.tts_engine.getProperty('voices')
        if voices and len(voices) > 1:
            voice = random.choice(voices)
            self.tts_engine.setProperty('voice', voice.id)
        
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
    
    def run_commentary_cycle(self):
        """Run one full cycle of recording and commentary."""
        # Record audio for a short duration (30-60 seconds is reasonable)
        recording_duration = min(60, self.interval // 2)  # Don't record for more than half the interval
        sound_detected = self.record_audio(recording_duration)
        
        if sound_detected:
            # Try to transcribe the audio
            transcription = self.transcribe_audio()
            
            # Get and speak commentary
            commentary = self.get_gemini_commentary(transcription)
            self.speak(commentary)
        else:
            print("No meaningful sound detected, skipping commentary")
    
    def run(self):
        """Run the passive listener in a loop."""
        print(f"Passive listener running with {self.interval // 60} minute intervals")
        print("Press Ctrl+C to exit")
        
        # Check if the main assistant is running
        self._check_for_main_assistant()
        
        try:
            while self.running:
                self.run_commentary_cycle()
                
                # Wait until next interval
                wait_time = self.interval - (60 if self.interval > 60 else self.interval // 2)
                print(f"Waiting {wait_time} seconds until next recording...")
                time.sleep(wait_time)
        
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            self.cleanup()
    
    def _check_for_main_assistant(self):
        """Check if the main voice assistant is running."""
        import subprocess
        
        # Look for any running raspai.py or raspai_advanced.py processes
        try:
            output = subprocess.check_output(["ps", "aux"]).decode("utf-8")
            if "raspai.py" in output or "raspai_advanced.py" in output:
                print("\n⚠️  WARNING: It appears that the main voice assistant is already running.")
                print("Running both the main assistant and passive listener simultaneously")
                print("may cause conflicts with audio devices and unexpected behavior.\n")
                
                response = input("Do you want to continue anyway? (y/n): ")
                if response.lower() != 'y':
                    print("Exiting. Please stop the main assistant before running the passive listener.")
                    self.cleanup()
                    sys.exit(0)
                print("Continuing with passive listener mode...\n")
        except Exception:
            # If we can't check, just continue
            pass
    
    def cleanup(self):
        """Clean up resources before exit."""
        if self.audio_feedback:
            self.audio_feedback.cleanup()
        
        if self.pyaudio:
            self.pyaudio.terminate()
        
        # Remove temporary audio file
        if os.path.exists(TEMP_AUDIO_FILE):
            os.remove(TEMP_AUDIO_FILE)

def parse_arguments():
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="RaspAI Passive Listener")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help="Minutes between commentaries (default: 5)")
    parser.add_argument("--harshness", type=int, choices=range(1, 6), default=DEFAULT_HARSHNESS,
                        help="Harshness level 1-5 (1=mild, 5=brutal, default: 3)")
    return parser.parse_args()

def main():
    """Main function to start the passive listener."""
    # Print a clear warning about not running this alongside the main assistant
    print("\n" + "=" * 70)
    print("⚠️  PASSIVE LISTENER MODE - DO NOT RUN WITH MAIN ASSISTANT")
    print("=" * 70)
    print("\nThis mode will periodically listen and make sarcastic comments.")
    print("It should NOT be run at the same time as the main voice assistant.")
    print("To use the normal voice assistant, exit this and run raspai.py instead.\n")
    
    args = parse_arguments()
    
    try:
        listener = PassiveListener(interval=args.interval, harshness=args.harshness)
        listener.run()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main() 
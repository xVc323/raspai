#!/usr/bin/env python3
"""
RaspAI Advanced - An enhanced Raspberry Pi Voice Assistant powered by Google's Gemini AI

This script creates an advanced voice assistant with:
1. Wake word detection
2. Audio feedback (beep sounds)
3. Conversation history
4. Built-in commands
5. Context-aware responses

Usage:
    python raspai_advanced.py

Requirements:
    See requirements.txt
"""

import os
import time
import json
import datetime
import wave
import numpy as np
import pyaudio
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
WAKE_WORD = "hey raspberry"  # Wake word to trigger the assistant
AUDIO_TIMEOUT = 7  # Seconds to listen for after wake word
SAMPLE_RATE = 16000  # Audio sample rate
CHANNELS = 1  # Mono audio
CHUNK = 1024  # Audio chunk size

# Conversation history settings
MAX_HISTORY_LENGTH = 10  # Maximum number of conversation turns to remember
HISTORY_FILE = "conversation_history.json"

# Commands
BUILT_IN_COMMANDS = {
    "stop": ["stop", "exit", "quit", "bye", "goodbye"],
    "time": ["what time is it", "tell me the time", "current time"],
    "date": ["what day is it", "tell me the date", "current date", "what's today's date"],
    "weather": ["weather", "forecast", "temperature"],  # Would need API integration
    "volume": ["volume up", "volume down", "increase volume", "decrease volume"],
    "restart": ["restart", "reboot"],
    "clear history": ["clear history", "forget conversation", "new conversation"]
}

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
    
    def error_sound(self):
        """Play a sound to indicate an error."""
        self.play_tone(220, 0.3)  # A3 (low tone)
    
    def cleanup(self):
        """Clean up resources."""
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

class ConversationHistory:
    """Class to manage conversation history."""
    
    def __init__(self, history_file=HISTORY_FILE, max_length=MAX_HISTORY_LENGTH):
        """Initialize the conversation history manager."""
        self.history_file = history_file
        self.max_length = max_length
        self.history = []
        self.load_history()
    
    def load_history(self):
        """Load conversation history from file if it exists."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
                    
                # Ensure it's not longer than max_length
                if len(self.history) > self.max_length:
                    self.history = self.history[-self.max_length:]
                    
                print(f"Loaded {len(self.history)} conversation turns from history.")
        except Exception as e:
            print(f"Error loading conversation history: {e}")
            self.history = []
    
    def save_history(self):
        """Save conversation history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Error saving conversation history: {e}")
    
    def add_interaction(self, user_query, assistant_response):
        """Add a new interaction to the history."""
        timestamp = datetime.datetime.now().isoformat()
        interaction = {
            "timestamp": timestamp,
            "user_query": user_query,
            "assistant_response": assistant_response
        }
        
        self.history.append(interaction)
        
        # Trim to max length
        if len(self.history) > self.max_length:
            self.history = self.history[-self.max_length:]
        
        # Save to file
        self.save_history()
    
    def clear(self):
        """Clear the conversation history."""
        self.history = []
        self.save_history()
        print("Conversation history cleared.")
    
    def get_recent_history(self, num_turns=3):
        """Get the N most recent conversation turns for context."""
        return self.history[-num_turns:] if len(self.history) > 0 else []
    
    def format_for_context(self, num_turns=3):
        """Format the conversation history for Gemini API context."""
        recent = self.get_recent_history(num_turns)
        if not recent:
            return ""
            
        context = "Previous conversation:\n"
        for i, item in enumerate(recent):
            context += f"User: {item['user_query']}\n"
            context += f"Assistant: {item['assistant_response']}\n"
        
        return context

class AdvancedVoiceAssistant:
    def __init__(self):
        """Initialize the advanced voice assistant."""
        self.recognizer = sr.Recognizer()
        
        # Initialize text-to-speech engine
        self.tts_engine = pyttsx3.init()
        
        # Adjust TTS properties
        self.tts_engine.setProperty('rate', 150)  # Speed of speech
        self.tts_engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        # Initialize the microphone
        self.microphone = sr.Microphone()
        
        # Initialize audio feedback
        self.audio_feedback = AudioFeedback()
        
        # Initialize conversation history
        self.conversation = ConversationHistory()
        
        # Flag to control main loop
        self.running = True
        
        # Calibrate recognizer for ambient noise
        with self.microphone as source:
            print("Calibrating for ambient noise... Please wait.")
            self.recognizer.adjust_for_ambient_noise(source, duration=3)
            print("Calibration complete. Ready to listen!")
    
    def listen_for_wake_word(self):
        """Listen for the wake word and return True if heard."""
        print(f"Listening for wake word: '{WAKE_WORD}'")
        
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=3)
                text = self.recognizer.recognize_google(audio).lower()
                print(f"Heard: {text}")
                
                if WAKE_WORD.lower() in text:
                    print("Wake word detected!")
                    self.audio_feedback.wake_sound()
                    time.sleep(0.2)
                    return True
            except sr.WaitTimeoutError:
                return False
            except sr.UnknownValueError:
                return False
            except Exception as e:
                print(f"Error: {e}")
                return False
        
        return False
    
    def listen_for_query(self):
        """Listen for user query after wake word detection."""
        print("Listening for your query...")
        self.audio_feedback.listening_sound()
        
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=AUDIO_TIMEOUT, phrase_time_limit=15)
                text = self.recognizer.recognize_google(audio)
                print(f"Query: {text}")
                return text
            except sr.UnknownValueError:
                print("Sorry, I didn't understand that.")
                self.speak("Sorry, I didn't understand that.")
                return None
            except sr.RequestError:
                print("Sorry, I couldn't request results. Check your network connection.")
                self.speak("Sorry, I couldn't process that. Check your network connection.")
                return None
            except Exception as e:
                print(f"Error: {e}")
                self.audio_feedback.error_sound()
                self.speak("Sorry, something went wrong.")
                return None
    
    def process_with_gemini(self, query):
        """Send the query to Gemini AI and get a response."""
        if not query:
            return "I didn't catch that. Can you try again?"
        
        # First, check for built-in commands
        command_response = self.check_for_commands(query)
        if command_response:
            return command_response
        
        try:
            self.audio_feedback.processing_sound()
            
            # Get recent conversation history for context
            context = self.conversation.format_for_context()
            
            # Prepare the prompt with context
            if context:
                full_prompt = f"{context}\nUser's new question: {query}\nRespond to the last question only."
            else:
                full_prompt = query
            
            # Generate content using Gemini AI
            response = model.generate_content(full_prompt)
            response_text = response.text
            print(f"Gemini response: {response_text}")
            
            # Add to history
            self.conversation.add_interaction(query, response_text)
            
            return response_text
        except Exception as e:
            print(f"Error processing with Gemini: {e}")
            self.audio_feedback.error_sound()
            return "Sorry, I encountered an error processing your request."
    
    def check_for_commands(self, query):
        """Check if the query matches any built-in commands."""
        query_lower = query.lower()
        
        # Check for stop command
        if any(cmd in query_lower for cmd in BUILT_IN_COMMANDS["stop"]):
            self.running = False
            return "Goodbye! Shutting down."
        
        # Check for time command
        if any(cmd in query_lower for cmd in BUILT_IN_COMMANDS["time"]):
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            return f"The current time is {current_time}."
        
        # Check for date command
        if any(cmd in query_lower for cmd in BUILT_IN_COMMANDS["date"]):
            current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {current_date}."
        
        # Check for clear history command
        if any(cmd in query_lower for cmd in BUILT_IN_COMMANDS["clear history"]):
            self.conversation.clear()
            return "I've cleared our conversation history."
        
        # No command matched
        return None
    
    def speak(self, text):
        """Convert text to speech and play it."""
        if not text:
            return
        
        print(f"Assistant: {text}")
        self.audio_feedback.response_sound()
        time.sleep(0.3)  # Short delay before speaking
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
    
    def run(self):
        """Main loop for the voice assistant."""
        print("RaspAI Advanced Voice Assistant started!")
        print(f"Say '{WAKE_WORD}' to start...")
        
        while self.running:
            if self.listen_for_wake_word():
                query = self.listen_for_query()
                if query:
                    response = self.process_with_gemini(query)
                    self.speak(response)
            
            # Small delay to reduce CPU usage
            time.sleep(0.1)
        
        print("Voice assistant shutting down.")
        self.cleanup()
    
    def cleanup(self):
        """Clean up resources before exit."""
        if self.audio_feedback:
            self.audio_feedback.cleanup()

def main():
    """Main function to start the voice assistant."""
    try:
        assistant = AdvancedVoiceAssistant()
        assistant.run()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main() 
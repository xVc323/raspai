#!/usr/bin/env python3
"""
RaspAI - A Raspberry Pi Voice Assistant powered by Google's Gemini AI

This script creates a voice assistant that:
1. Listens for a wake word
2. Records audio
3. Sends audio to Gemini AI for processing
4. Converts the response to speech
5. Plays the response

Usage:
    python raspai.py

Requirements:
    See requirements.txt
"""

import os
import time
import json
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
AUDIO_TIMEOUT = 5  # Seconds to listen for after wake word
SAMPLE_RATE = 16000  # Audio sample rate
CHANNELS = 1  # Mono audio
CHUNK = 1024  # Audio chunk size

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

class VoiceAssistant:
    def __init__(self):
        """Initialize the voice assistant."""
        self.recognizer = sr.Recognizer()
        
        # Initialize text-to-speech engine
        self.tts_engine = pyttsx3.init()
        
        # Adjust TTS properties
        self.tts_engine.setProperty('rate', 150)  # Speed of speech
        self.tts_engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        # Initialize the microphone
        self.microphone = sr.Microphone()
        
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
                    self.speak("How can I help you?")
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
        
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=AUDIO_TIMEOUT, phrase_time_limit=10)
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
                self.speak("Sorry, something went wrong.")
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
    
    def speak(self, text):
        """Convert text to speech and play it."""
        if not text:
            return
        
        print(f"Assistant: {text}")
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
    
    def run(self):
        """Main loop for the voice assistant."""
        print("RaspAI Voice Assistant started!")
        print(f"Say '{WAKE_WORD}' to start...")
        
        while True:
            if self.listen_for_wake_word():
                query = self.listen_for_query()
                if query:
                    response = self.process_with_gemini(query)
                    self.speak(response)
            
            # Small delay to reduce CPU usage
            time.sleep(0.1)

def main():
    """Main function to start the voice assistant."""
    try:
        assistant = VoiceAssistant()
        assistant.run()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main() 
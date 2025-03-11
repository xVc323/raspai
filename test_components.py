#!/usr/bin/env python3
"""
RaspAI Test Components

This script tests the various components of the RaspAI voice assistant to ensure
they are working correctly before running the full assistant.

Usage:
    python3 test_components.py
"""

import os
import sys
import time
import pyaudio
import numpy as np
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
from dotenv import load_dotenv

def print_header(text):
    """Print a header with the given text."""
    print("\n" + "=" * 50)
    print(f"{text}")
    print("=" * 50)

def test_audio_output():
    """Test audio output by playing a series of tones."""
    print_header("TESTING AUDIO OUTPUT")
    print("You should hear a series of tones...")
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    try:
        # Generate a sine wave for the test tone
        sample_rate = 44100
        duration = 0.3
        frequencies = [262, 330, 392, 523]  # C4, E4, G4, C5
        
        for freq in frequencies:
            # Generate sine wave
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            tone = np.sin(freq * 2 * np.pi * t) * 0.5
            
            # Convert to the required format
            audio_data = (tone * 32767).astype(np.int16).tobytes()
            
            # Play the tone
            stream = p.open(
                format=p.get_format_from_width(2),
                channels=1,
                rate=sample_rate,
                output=True
            )
            stream.write(audio_data)
            stream.stop_stream()
            stream.close()
            time.sleep(0.1)
        
        print("✅ Audio output test complete. Did you hear the tones? (y/n)")
        if input().lower() != 'y':
            print("❌ Audio output test failed. Please check your speakers/headphones.")
        else:
            print("✅ Audio output test passed!")
    
    except Exception as e:
        print(f"❌ Audio output test failed: {e}")
    finally:
        p.terminate()

def test_microphone():
    """Test microphone by recording a short audio sample."""
    print_header("TESTING MICROPHONE")
    print("Please say something after the prompt...")
    
    recognizer = sr.Recognizer()
    
    try:
        with sr.Microphone() as source:
            print("Adjusting for ambient noise... Please be silent.")
            recognizer.adjust_for_ambient_noise(source, duration=2)
            print("Now speak something...")
            
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                print("Processing audio...")
                text = recognizer.recognize_google(audio)
                print(f"I heard: {text}")
                print("✅ Microphone test passed!")
            except sr.WaitTimeoutError:
                print("❌ Microphone test failed: No speech detected")
            except sr.UnknownValueError:
                print("❌ Microphone test failed: Could not understand audio")
            except sr.RequestError:
                print("❌ Microphone test failed: Google Speech Recognition service unavailable")
    
    except Exception as e:
        print(f"❌ Microphone test failed: {e}")

def test_tts():
    """Test text-to-speech functionality."""
    print_header("TESTING TEXT-TO-SPEECH")
    print("You should hear a voice saying a test phrase...")
    
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)
        
        test_text = "This is a test of the Raspberry Pi voice assistant text to speech system."
        print(f"Speaking: '{test_text}'")
        
        engine.say(test_text)
        engine.runAndWait()
        
        print("✅ TTS test complete. Did you hear the voice? (y/n)")
        if input().lower() != 'y':
            print("❌ TTS test failed. Please check your speakers/headphones.")
        else:
            print("✅ TTS test passed!")
    
    except Exception as e:
        print(f"❌ TTS test failed: {e}")

def test_gemini_api():
    """Test the Gemini API connection."""
    print_header("TESTING GEMINI API")
    print("Testing connection to Google's Gemini API...")
    
    # Load environment variables
    load_dotenv()
    
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("❌ Gemini API test failed: API key not found in .env file")
            return
        
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        # Generate a test response
        print("Generating test response from Gemini...")
        response = model.generate_content("Respond with a short greeting and mention you're running on a Raspberry Pi.")
        
        print(f"Gemini response: {response.text}")
        print("✅ Gemini API test passed!")
    
    except Exception as e:
        print(f"❌ Gemini API test failed: {e}")

def main():
    """Run all component tests."""
    print_header("RASPAI COMPONENT TESTS")
    print("This script will test all components of your RaspAI voice assistant.")
    print("Follow the prompts to test each component.")
    
    # Ask which tests to run
    print("\nWhich tests would you like to run?")
    print("1. All tests")
    print("2. Audio output test only")
    print("3. Microphone test only")
    print("4. Text-to-speech test only")
    print("5. Gemini API test only")
    choice = input("Enter your choice (1-5): ")
    
    if choice == '1' or choice == '2':
        test_audio_output()
        
    if choice == '1' or choice == '3':
        test_microphone()
        
    if choice == '1' or choice == '4':
        test_tts()
        
    if choice == '1' or choice == '5':
        test_gemini_api()
    
    print("\nComponent tests complete!")
    print("If all tests passed, you're ready to run the full voice assistant.")
    print("Run 'python3 raspai.py' or 'python3 raspai_advanced.py' to start.\n")

if __name__ == "__main__":
    main() 
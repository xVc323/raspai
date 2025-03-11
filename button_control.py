#!/usr/bin/env python3
"""
Button control for RaspAI Voice Assistant

This script allows controlling the voice assistant with a physical button 
connected to the Raspberry Pi GPIO pins.

Usage:
    python button_control.py
    
Hardware connection:
    - Connect one end of a momentary push button to GPIO pin 17
    - Connect the other end to GND
    - A pull-up resistor is not needed as we use the internal one

Requirements:
    - RPi.GPIO
"""

import os
import time
import signal
import sys
import subprocess
import RPi.GPIO as GPIO

# GPIO Pin configuration
BUTTON_PIN = 17  # GPIO pin for the button
LED_PIN = 27     # Optional: GPIO pin for LED indicator

# Command to run the voice assistant
ASSISTANT_COMMAND = "python3 raspai.py"

class ButtonController:
    def __init__(self):
        """Initialize the button controller."""
        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Set up LED if used
        if LED_PIN:
            GPIO.setup(LED_PIN, GPIO.OUT)
            GPIO.output(LED_PIN, GPIO.LOW)
        
        # Variable to store the process
        self.assistant_process = None
        
        # Register signal handlers for clean exit
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        print("Button controller initialized")
        print(f"Press the button on GPIO {BUTTON_PIN} to start/stop the assistant")
    
    def start_assistant(self):
        """Start the voice assistant as a subprocess."""
        if self.assistant_process is None or self.assistant_process.poll() is not None:
            print("Starting voice assistant...")
            if LED_PIN:
                GPIO.output(LED_PIN, GPIO.HIGH)
            
            # Start the assistant as a subprocess
            self.assistant_process = subprocess.Popen(
                ASSISTANT_COMMAND.split(), 
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            print("Voice assistant started")
            return True
        return False
    
    def stop_assistant(self):
        """Stop the voice assistant subprocess."""
        if self.assistant_process and self.assistant_process.poll() is None:
            print("Stopping voice assistant...")
            if LED_PIN:
                GPIO.output(LED_PIN, GPIO.LOW)
            
            # Terminate the process
            self.assistant_process.terminate()
            try:
                self.assistant_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force killing assistant process...")
                self.assistant_process.kill()
            
            self.assistant_process = None
            print("Voice assistant stopped")
            return True
        return False
    
    def toggle_assistant(self):
        """Toggle the voice assistant on/off."""
        if self.assistant_process and self.assistant_process.poll() is None:
            return self.stop_assistant()
        else:
            return self.start_assistant()
    
    def run(self):
        """Main loop to monitor button presses."""
        last_button_state = GPIO.input(BUTTON_PIN)
        debounce_time = 0.3  # seconds
        last_press_time = 0
        
        print("Button controller running. Press Ctrl+C to exit.")
        
        try:
            while True:
                # Read button state
                button_state = GPIO.input(BUTTON_PIN)
                
                # Button press detected (button connected to GND when pressed)
                if button_state == GPIO.LOW and last_button_state == GPIO.HIGH:
                    current_time = time.time()
                    if current_time - last_press_time > debounce_time:
                        print("Button pressed")
                        self.toggle_assistant()
                        last_press_time = current_time
                
                last_button_state = button_state
                time.sleep(0.1)  # Small delay to reduce CPU usage
        
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            self.cleanup()
    
    def cleanup(self, *args):
        """Clean up GPIO and processes before exit."""
        print("Cleaning up...")
        if self.assistant_process:
            self.stop_assistant()
        GPIO.cleanup()
        sys.exit(0)

def main():
    """Main function to start the button controller."""
    controller = ButtonController()
    controller.run()

if __name__ == "__main__":
    main() 
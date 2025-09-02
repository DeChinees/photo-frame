#!/usr/bin/env python3
import time
import spidev
import RPi.GPIO as GPIO
from PIL import Image
from waveshare_epd import epd7in3e

# Define GPIO pins used by the e-Paper HAT
RST_PIN = 17
DC_PIN = 25
CS_PIN = 8
BUSY_PIN = 24

def setup_gpio():
    """Setup GPIO with proper cleanup"""
    GPIO.setwarnings(False)  # Disable warnings
    GPIO.cleanup()  # Clean up first
    GPIO.setmode(GPIO.BCM)
    return check_gpio()

def check_gpio():
    """Verify GPIO setup"""
    try:
        GPIO.setup(RST_PIN, GPIO.OUT)
        GPIO.setup(DC_PIN, GPIO.OUT)
        GPIO.setup(CS_PIN, GPIO.OUT)
        GPIO.setup(BUSY_PIN, GPIO.IN)
        print("GPIO setup successful")
        return True
    except Exception as e:
        print(f"GPIO Error: {e}")
        return False

def check_busy_pin():
    """Check if BUSY pin is responding"""
    try:
        state = GPIO.input(BUSY_PIN)
        print(f"BUSY pin state: {state}")
        return True
    except Exception as e:
        print(f"BUSY pin error: {e}")
        return False

def check_spi():
    """Verify SPI is working"""
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)  # Bus 0, Device 0
        spi.max_speed_hz = 4000000
        spi.mode = 0
        print("SPI connection successful")
        spi.close()
        return True
    except Exception as e:
        print(f"SPI Error: {e}")
        return False

def main():
    try:
        # Check GPIO first with proper setup
        if not setup_gpio():
            print("GPIO setup failed. Are you running with sudo?")
            return

        # Check SPI
        if not check_spi():
            print("SPI interface not available. Check if SPI is enabled.")
            return

        # Check BUSY pin
        if not check_busy_pin():
            print("BUSY pin not responding. Check connections.")
            return

        print("Creating EPD object...")
        epd = epd7in3e.EPD()
        
        print("Starting initialization...")
        epd.init()
        print("Initialization complete")

        # Test with smaller image first
        test_size = (100, 100)
        print(f"Creating test image {test_size}...")
        test_img = Image.new("RGB", test_size, (255, 0, 0))
        
        print("Converting to display buffer...")
        buffer = epd.getbuffer(test_img)
        
        print("Sending to display...")
        epd.display(buffer)

        print("Waiting 5 seconds...")
        time.sleep(5)

        print("Clearing display...")
        epd.clear()

        print("Going to sleep...")
        epd.sleep()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("Cleanup...")
        try:
            GPIO.cleanup()
        except:
            pass

if __name__ == "__main__":
    main()
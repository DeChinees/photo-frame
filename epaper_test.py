#!/usr/bin/env python3
import time
import spidev
import RPi.GPIO as GPIO
from PIL import Image
from waveshare_epd import epd7in3e

def check_spi():
    """Verify SPI is working"""
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)  # Bus 0, Device 0
        print("SPI connection successful")
        spi.close()
        return True
    except Exception as e:
        print(f"SPI Error: {e}")
        return False

def main():
    try:
        # Check SPI first
        if not check_spi():
            print("SPI interface not available. Check if SPI is enabled.")
            return

        print("Creating EPD object...")
        epd = epd7in3e.EPD()
        
        print("Starting initialization...")
        epd.init()
        print("Initialization complete")

        W, H = epd.width, epd.height
        print(f"Display size: {W}x{H}")

        print("Creating red image...")
        red_img = Image.new("RGB", (W, H), (255, 0, 0))
        
        print("Converting to display buffer...")
        buffer = epd.getbuffer(red_img)
        
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
        
    finally:
        print("Cleanup...")
        try:
            epd.sleep()
        except:
            pass
        GPIO.cleanup()

if __name__ == "__main__":
    main()
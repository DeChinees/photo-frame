#!/usr/bin/env python3
import time
from PIL import Image
from waveshare_epd import epd7in3e   # driver for 7.3" e-Paper (E)

def main():
    try:
        epd = epd7in3e.EPD()
        print("Init...")
        epd.init()

        W, H = epd.width, epd.height

        print("Fill RED...")
        red_img = Image.new("RGB", (W, H), (255, 0, 0))
        epd.display(epd.getbuffer(red_img))

        time.sleep(5)

        print("Clear (white)...")
        epd.clear()

        print("Sleep...")
        epd.sleep()

    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        # Make sure display goes to sleep even if there's an error
        try:
            epd.sleep()
        except:
            pass

if __name__ == "__main__":
    main()
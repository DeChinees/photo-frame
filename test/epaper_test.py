#!/usr/bin/env python3
import logging
from waveshare_epd import epd7in3e
import time
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.DEBUG)

try:
    logging.info("epaper test start")

    epd = epd7in3e.EPD()
    logging.info("init")
    epd.init()

    logging.info("Clear...")
    epd.Clear()

    # Create new image with red color
    logging.info("Drawing red image...")
    image = Image.new('RGB', (epd.width, epd.height), 'red')
    epd.display(epd.getbuffer(image))
    logging.info("Showing red image...")

    time.sleep(2)

    logging.info("Clear...")
    epd.Clear()

    logging.info("Goto Sleep...")
    epd.sleep()

except IOError as e:
    logging.info(e)

except KeyboardInterrupt:
    logging.info("ctrl + c:")
    epd7in3e.epdconfig.module_exit()
    exit()
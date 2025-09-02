# E-Paper Photo Frame

Display photos on a Waveshare 7.3" e-Paper HAT (E) using a Raspberry Pi. The script automatically handles image resizing, color conversion, and dithering to match the e-Paper display's capabilities.

## Features

- Supports common image formats (JPG, PNG, etc.)
- Automatically resizes images to 800x480
- Converts images to 6-color Spectra palette (White, Black, Red, Yellow, Blue, Green)
- Uses Floyd-Steinberg dithering for optimal visual quality
- Supports image rotation
- Powers down display after image is shown

## Hardware Requirements

- Raspberry Pi (any model)
- Waveshare 7.3" e-Paper HAT (E)
- MicroSD card (8GB+ recommended)

## Installation

### 1. Basic Setup

First, ensure your Raspberry Pi is up to date:
```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Enable SPI

The e-Paper display uses SPI interface:
```bash
sudo raspi-config nonint do_spi 0
```

### 3. Install Python and Dependencies

Install Python and required tools:
```bash
sudo apt install -y python3-pip python3-venv python3-pil
```

Install pipx:
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Log out and back in, then install required packages:
```bash
pipx install RPi.GPIO
pipx install spidev
```

### 4. Install Waveshare Driver

Clone the Waveshare repository:
```bash
cd ~
git clone https://github.com/waveshare/e-Paper.git
```

### 5. Install This Project

Clone this project:
```bash
cd ~
git clone [your-repository-url] photo-frame
cd photo-frame
```

Create symbolic link to Waveshare library:
```bash
ln -s ~/e-Paper/RaspberryPi_JetsonNano/python/lib lib
```

## Usage

Basic usage:
```bash
python3 epaper_show.py path/to/image.jpg
```

With rotation:
```bash
python3 epaper_show.py path/to/image.jpg --rotate 90
```

Rotation options:
- `0`: No rotation (default)
- `90`: Rotate 90 degrees clockwise
- `180`: Rotate 180 degrees
- `270`: Rotate 270 degrees clockwise

## Image Processing

The script automatically:
1. Resizes the image to fit the 800x480 display
2. Centers and crops the image to fill the screen
3. Converts colors to the 6-color palette using dithering
4. Sends the processed image to the display

## Troubleshooting

### Permission Issues

If you get permission errors, add your user to the required groups:
```bash
sudo usermod -a -G spi,gpio $USER
```
Then log out and back in.

### Display Not Working

1. Check SPI is enabled:
```bash
lsmod | grep spi
```

2. Verify connections:
- BUSY -> GPIO 24
- RST -> GPIO 17
- DC -> GPIO 25
- CS -> GPIO 8
- CLK -> SPI CLK
- DIN -> SPI MOSI
- GND -> GND
- VCC -> 3.3V

### Module Not Found

If you get "No module named 'waveshare_epd'", check that:
1. The symbolic link to the library exists
2. You're running the script from the project directory

## Power Consumption

The e-Paper display only uses power when updating the image. Once the image is displayed and the panel is put to sleep, it consumes no power to maintain the image.

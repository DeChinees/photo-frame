#!/bin/bash

# Exit on error
set -e

echo "Installing Photo Frame..."

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "This script must be run on a Raspberry Pi"
    exit 1
fi

# Update system
echo "Updating system..."
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-pil

# Enable SPI
echo "Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# Create virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Clone Waveshare e-Paper library if not exists
if [ ! -d "e-Paper" ]; then
    echo "Downloading Waveshare e-Paper library..."
    git clone https://github.com/waveshare/e-Paper.git
    ln -s e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd .
fi

# Set up service directories
echo "Creating required directories..."
mkdir -p photos_src photos_ready thumbs

# Set permissions
echo "Setting up permissions..."
sudo usermod -a -G spi,gpio $USER

# Create systemd service for web interface
echo "Creating systemd service..."
sudo tee /etc/systemd/system/photoframe.service > /dev/null << EOL
[Unit]
Description=Photo Frame Web Interface
After=network.target

[Service]
ExecStart=$(pwd)/venv/bin/python $(pwd)/webframe.py
WorkingDirectory=$(pwd)
Environment=FRAME_TOKEN=changeme123
User=$USER
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Enable and start service
sudo systemctl enable photoframe
sudo systemctl start photoframe

echo "Installation complete!"
echo "Please reboot your Raspberry Pi to ensure all changes take effect."
echo "Default web interface will be available at: http://$(hostname):5000"
echo "Default token is: changeme123"
echo "Change the token by editing /etc/systemd/system/photoframe.service"
echo ""
echo "To reboot now, type: sudo reboot"
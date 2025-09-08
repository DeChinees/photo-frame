import spidev
import os

def check_spi_device():
    """Check if SPI device exists"""
    if os.path.exists('/dev/spidev0.0'):
        print("SPI device found at /dev/spidev0.0")
        return True
    else:
        print("SPI device not found!")
        return False

def check_spi_permissions():
    """Check SPI permissions"""
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)
        print("Successfully opened SPI device")
        print(f"Max speed: {spi.max_speed_hz}")
        print(f"Mode: {spi.mode}")
        spi.close()
        return True
    except Exception as e:
        print(f"SPI Error: {e}")
        return False

def main():
    print("=== SPI Test ===")
    print("\nChecking SPI device...")
    if not check_spi_device():
        return

    print("\nChecking SPI permissions...")
    if not check_spi_permissions():
        return

    print("\nSPI access test successful!")

if __name__ == "__main__":
    main()
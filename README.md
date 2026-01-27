# PSU-DMM PyVISA Data Capture

This simple Python program is designed to automate voltage sweeps and data logging using Keysight bench equipment. It controls a Power Supply Unit (PSU) to step through a voltage range while recording voltage measurements from a Digital Multimeter (DMM).

## Supported Instruments

- **Power Supply:** Keysight E36313A 
  - *(Will probably work with similar models too)*
- **Digital Multimeter:** Keysight EDU34450A
  - *(Will probably work with similar models too)*

## Features

- **GUI Control:** Built with Tkinter for easy config.
- **Automated Sweeps:** Configurable start voltage, stop voltage, step size, and settle time.
- **Data Logging:** Automatically saves data to CSV files.
- **Instrument Discovery:** Scans and lists connected VISA resources.

## Example Image:
![Example Image](example.png)

## Quick Setup (Windows)

The included PowerShell script handles environment setup and dependency installation automatically.

1. Open PowerShell in this directory.
2. Run the launch script:
   ```powershell
   .\launch.ps1
   ```
   - This will create a virtual environment, install the required dependencies, and launch the application.

## Manual Setup

1. Install Python (3.x). Either from [Python.org](https://www.python.org/downloads/) or via the [Microsoft Store](https://apps.microsoft.com/search?query=Python).
2. Open a PowerShell terminal and navigate to the install directory.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: You must have a [VISA backend](https://pyvisa.readthedocs.io/en/latest/introduction/getting.html#backend) installed (like NI-VISA or Keysight IO Libraries Suite) for PyVISA to communicate with instruments.*
4. Run the script:
   ```bash
   python visa_logger.py
   ```


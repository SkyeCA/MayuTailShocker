@echo off
echo ========================================
echo  Mayu Tail Shock Controller Build
echo ========================================

REM Check if the virtual environment exists by looking for the activate script
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Creating "venv"...
    python -m venv venv
    
    echo [!] Activating virtual environment...
    call venv\Scripts\activate.bat
    
    echo [!] Installing dependencies...
    pip install -r requirements.txt
    
    echo [!] Installing PyInstaller...
    pip install pyinstaller pillow
) ELSE (
    echo [*] Virtual environment found. Activating...
    call venv\Scripts\activate.bat
)

echo [*] Building EXE with PyInstaller...

REM Run PyInstaller with the following flags:
REM --noconfirm: Overwrite existing build folders automatically
REM --onefile: Bundle everything into a single .exe
REM --windowed: Hide the background command prompt window when running
REM --icon: Apply the custom icon to the .exe file itself
REM --add-data: Bundle the icon image into the exe so Tkinter can load it later

pyinstaller --noconfirm --onefile --windowed --icon="resources\icon.png" --add-data="resources\icon.png;resources" tail_shocker.py

echo ========================================
echo  Build Complete! 
echo  The new EXE is located in the ./dist folder.
echo ========================================
pause
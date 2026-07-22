@echo off
echo ========================================
echo  Mayu Tail Shocker Build
echo ========================================

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

pyinstaller -n "MayuTailShocker" --noconsole --onefile --icon=resources/icon.png --add-data "resources/icon.png;resources" --version-file=version_info.txt tail_shocker.py

echo [*] Signing the Executable...

powershell -NoProfile -Command ^
    "$certName = 'CN=MayuTailShocker'; " ^
    "$cert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Subject -eq $certName } | Select-Object -First 1; " ^
    "if (-not $cert) { " ^
    "    Write-Host 'Generating new self-signed certificate...'; " ^
    "    $cert = New-SelfSignedCertificate -Subject $certName -Type CodeSigningCert -CertStoreLocation 'Cert:\CurrentUser\My'; " ^
    "} else { " ^
    "    Write-Host 'Found existing certificate, reusing...'; " ^
    "} " ^
    "$rootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'CurrentUser'); " ^
    "$rootStore.Open('ReadWrite'); " ^
    "$trusted = $rootStore.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }; " ^
    "if (-not $trusted) { " ^
    "    Write-Host 'Adding certificate to Trusted Root (Please click YES on the Windows popup)...' -ForegroundColor Yellow; " ^
    "    $rootStore.Add($cert); " ^
    "} " ^
    "$rootStore.Close(); " ^
    "Write-Host 'Signing dist\MayuTailShocker.exe...'; " ^
    "$sig = Set-AuthenticodeSignature -FilePath '.\dist\MayuTailShocker.exe' -Certificate $cert -TimestampServer 'http://timestamp.digicert.com'; " ^
    "if ($sig.Status -eq 'Valid') { Write-Host 'Signature applied successfully!' -ForegroundColor Green } " ^
    "else { Write-Host ('Signature failed: ' + $sig.StatusMessage) -ForegroundColor Red }"

echo ========================================
echo  Build Complete! 
echo  The new EXE is located in the ./dist folder.
echo ========================================
pause
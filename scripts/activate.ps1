# This script activates the Python virtual environment and sets the Finnhub API key.
# It should be run from the project root directory.

# --- Configuration ---
$VenvPath = "$PSScriptRoot\..\venv"
$EnvFilePath = "$PSScriptRoot\..\.env"

# --- 1. Check if the virtual environment exists ---
if (-not (Test-Path $VenvPath -PathType Container)) {
    Write-Host "Virtual environment not found at '$VenvPath'."
    Write-Host "Please run the main setup script first."
    # You might want to automatically call the setup script here
    # & .\setup_env.ps1
    return
}

# --- 2. Activate the virtual environment ---
try {
    . "$VenvPath\Scripts\Activate.ps1"
    Write-Host "Virtual environment activated."
} catch {
    Write-Error "Failed to activate virtual environment. Make sure you are running this script with PowerShell."
    return
}

# --- 3. Load the API key from .env file ---
if (-not (Test-Path $EnvFilePath)) {
    Write-Warning "'.env' file not found at '$EnvFilePath'."
    Write-Warning "Please copy '.env.example' to '.env' and add your Finnhub API key."
    return
}

try {
    # Get content and parse both keys
    $content = Get-Content $EnvFilePath -Raw

    # Match standard API key
    $apiKeyMatch = [regex]::Match($content, 'FINNHUB_API_KEY\s*=\s*["'']?([^"''\s]+)["'']?')
    if ($apiKeyMatch.Success) {
        $apiKey = $apiKeyMatch.Groups[1].Value
        if ($apiKey -and $apiKey -ne "YOUR_FINNHUB_API_KEY_HERE") {
            $env:FINNHUB_API_KEY = $apiKey
            Write-Host "FINNHUB_API_KEY environment variable set successfully."
        } else {
            Write-Warning "FINNHUB_API_KEY is not set in your .env file. Please update it."
        }
    } else {
        Write-Warning "Could not find FINNHUB_API_KEY in the .env file."
    }

    # Match premium API key
    $premiumKeyMatch = [regex]::Match($content, 'FINNHUB_PREMIUM_KEY\s*=\s*["'']?([^"''\s]+)["'']?')
    if ($premiumKeyMatch.Success) {
        $premiumKey = $premiumKeyMatch.Groups[1].Value
        if ($premiumKey -and $premiumKey -ne "YOUR_PREMIUM_KEY_HERE") {
            $env:FINNHUB_PREMIUM_KEY = $premiumKey
            Write-Host "FINNHUB_PREMIUM_KEY environment variable set successfully."
        } else {
            Write-Warning "FINNHUB_PREMIUM_KEY is not set in your .env file. Please update it."
        }
    } else {
        Write-Warning "Could not find FINNHUB_PREMIUM_KEY in the .env file."
    }
} catch {
    Write-Error "An error occurred while reading the .env file."
}

Write-Host "Environment is ready. You can now run the project scripts."

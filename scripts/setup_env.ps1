# This script sets up the Python virtual environment for the Taihang-llm project.

# Get the project root directory (parent of scripts directory)
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = "$ProjectRoot\venv"

# 1. Create a virtual environment named 'venv' in the project root
python -m venv $VenvPath

# 2. Activate the virtual environment
# In PowerShell, you need to allow script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
& "$VenvPath\Scripts\Activate.ps1"

# 3. Install the required libraries
pip install pandas pandas-ta numpy scipy scikit-learn openai finnhub-python python-dotenv requests aiohttp 

# 4. Set the Finnhub API Key as an environment variable
# IMPORTANT: Replace "YOUR_FINNHUB_API_KEY" with your actual Finnhub API key.
$Env:FINNHUB_API_KEY = "d5jsub1r01qjaedrkpigd5jsub1r01qjaedrkpj0"

Write-Host "Environment setup complete."
Write-Host "To activate the environment in the future, run: .\scripts\activate.ps1"
Write-Host "Your FINNHUB_API_KEY is now set for this terminal session."
Write-Host "To make it permanent, you can set it in your system's environment variables."

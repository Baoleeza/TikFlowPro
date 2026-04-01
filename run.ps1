# Start FastAPI server in a new PowerShell window and open browser to the UI (port 8001)
# Ensures a local virtualenv exists and installs requirements if needed, then runs uvicorn from it.
$venv = Join-Path -Path (Get-Location) -ChildPath '.venv'
if (-not (Test-Path $venv)) {
	Write-Host "Creating virtual environment .venv..."
	python -m venv .venv
	$py = Join-Path $venv 'Scripts\python.exe'
	if (Test-Path $py) {
		Write-Host "Upgrading pip and installing requirements..."
		& $py -m pip install --upgrade pip
		if (Test-Path 'requirements.txt') {
			& $py -m pip install -r requirements.txt
		}
	}
}

$py = Join-Path $venv 'Scripts\python.exe'
if (Test-Path $py) {
	$cmd = "& `"$py`" -m uvicorn main:app --reload --host 127.0.0.1 --port 8001"
	Start-Process -FilePath powershell -ArgumentList '-NoExit','-Command',$cmd
} else {
	Start-Process powershell -ArgumentList '-NoExit','-Command','python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001'
}
Start-Sleep -Seconds 1
Start-Process "http://127.0.0.1:8001/"

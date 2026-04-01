@echo off
REM Start FastAPI server in a new console and open browser to the UI (port 8001)
REM Ensures a local virtualenv exists and installs requirements if needed.
setlocal
if not exist .venv (
	echo Creating virtual environment .venv...
	python -m venv .venv
	if exist .venv\Scripts\python.exe (
		echo Upgrading pip and installing requirements...
		.venv\Scripts\python.exe -m pip install --upgrade pip
		if exist requirements.txt (
			.venv\Scripts\python.exe -m pip install -r requirements.txt
		)
	)
)

echo Starting FastAPI (uvicorn) in new window...
start "FastAPI" cmd /k ".venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8001"
timeout /t 1 >nul
start "" "http://127.0.0.1:8001/"
endlocal
exit /b

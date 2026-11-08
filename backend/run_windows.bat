@echo off
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo Python is required. Install Python 3.12 or newer and try again.
        pause
        exit /b 1
    )
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)
if not exist venv (
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)
call venv\Scripts\activate
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Could not install backend dependencies.
    pause
    exit /b 1
)
echo.
echo Open  http://127.0.0.1:5000/login.html  in your browser
echo.
python app.py
pause

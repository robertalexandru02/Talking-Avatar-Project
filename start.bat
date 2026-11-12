@echo off
setlocal
cd /d "%~dp0"
if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" -B "%~dp0start.py" %*
    goto finish
)
for %%V in (3.12 3.11 3.10) do (
    py -%%V -c "pass" >nul 2>&1
    if not errorlevel 1 (
        py -%%V -B "%~dp0start.py" %*
        goto finish
    )
)
where python >nul 2>&1
if errorlevel 1 (
    echo Instaleaza Python 3.10-3.12 de la https://www.python.org/downloads/
    pause
    exit /b 1
)
python -B "%~dp0start.py" %*
:finish
if errorlevel 1 (
    echo.
    echo Pornirea nu a reusit. Verifica mesajul de mai sus.
    pause
    exit /b 1
)
endlocal
exit /b 0

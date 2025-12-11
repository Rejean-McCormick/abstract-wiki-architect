@echo off
REM Abstract Wikipedia - Build & Test Pipeline

echo ==========================================
echo [1/3] Running Build Orchestrator...
echo       (Forging Grammars + Compiling PGF)
echo ==========================================
python build_orchestrator.py
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Orchestration failed. Aborting pipeline.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==========================================
echo [2/3] Syncing Configuration...
echo ==========================================
python sync_config_from_gf.py
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Config sync failed. Aborting pipeline.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==========================================
echo [3/3] Verifying Build (Dynamic Test)...
echo ==========================================
python test_gf_dynamic.py
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Verification failed. Check the logs above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==========================================
echo [SUCCESS] Build Complete. System is ready!
echo ==========================================
pause
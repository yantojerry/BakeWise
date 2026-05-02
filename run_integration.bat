@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON="
set "PY_ARGS="
set "INSTALL_PYTHON="
set "INSTALL_ARGS="
set "TEST_TARGET=tests"

pushd "%ROOT%"

if exist "%ROOT%.venv\Scripts\python.exe" (
    set "INSTALL_PYTHON=%ROOT%.venv\Scripts\python.exe"
    "%ROOT%.venv\Scripts\python.exe" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON=%ROOT%.venv\Scripts\python.exe"
    )
)

if not defined PYTHON if exist "%ROOT%bakewise-test\bin\python.exe" (
    if not defined INSTALL_PYTHON (
        set "INSTALL_PYTHON=%ROOT%bakewise-test\bin\python.exe"
    )
    "%ROOT%bakewise-test\bin\python.exe" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON=%ROOT%bakewise-test\bin\python.exe"
    )
)

if not defined PYTHON (
    where py >nul 2>nul
    if not errorlevel 1 (
        if not defined INSTALL_PYTHON (
            set "INSTALL_PYTHON=py"
            set "INSTALL_ARGS=-3"
        )
        py -3 -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON=py"
            set "PY_ARGS=-3"
        )
    )
)

if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 (
        if not defined INSTALL_PYTHON (
            set "INSTALL_PYTHON=python"
        )
        python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON=python"
        )
    )
)

if not defined PYTHON (
    if defined INSTALL_PYTHON (
        echo pytest is not installed for any detected Python interpreter.
        echo.
        echo Install it with:
        echo   "%INSTALL_PYTHON%" %INSTALL_ARGS% -m pip install pytest
    ) else (
        echo Could not find a Python interpreter for integration tests.
        echo Checked:
        echo   %ROOT%.venv\Scripts\python.exe
        echo   %ROOT%bakewise-test\bin\python.exe
        echo   py -3
        echo   python
    )
    pause
    popd
    exit /b 1
)

echo Running integration tests...
echo.
"%PYTHON%" %PY_ARGS% -m pytest "%TEST_TARGET%" -v
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Integration tests passed.
) else (
    echo Integration tests failed with exit code %EXIT_CODE%.
)

pause
popd
exit /b %EXIT_CODE%

:: Creates a dedicated Conda environment with this package installed and ready to run in that environment.
::
:: Usage: install.bat [-e]
::
:: Use the optional -e argument to install in editable mode. In that case, any
:: change in the source code will be immediately reflected at execution, and the source folder
:: must not be moved or deleted after installation.


@echo off
setlocal
pushd "%~dp0"

set "EXTRA_PIP_INSTALL_OPTIONS="
if /I "%~1"=="-e" set "EXTRA_PIP_INSTALL_OPTIONS=--editable"

where pixi >nul 2>nul
if errorlevel 1 (
  echo "** ERROR: Pixi was not found on PATH **"
  popd
  exit /B 1
)

pixi install --environment runtime
if errorlevel 1 (
  echo "** ERROR: Pixi environment installation failed **"
  popd
  exit /B 1
)

pixi run --environment runtime uv pip install --python ".pixi\envs\runtime\python.exe" --no-deps %EXTRA_PIP_INSTALL_OPTIONS% .
if errorlevel 1 (
  echo "** ERROR: Package installation failed **"
  popd
  exit /B 1
)

pixi shell --environment runtime
popd

:: Creates a dedicated environment for using this package under the Python environment location
:: used by Geoscience Analyst.
:: Assumes Analyst is installed under "%ProgramFiles%\Mira Geoscience\Geoscience ANALYST".
::
:: Usage: install_in_analyst.bat [-e] [--conda default] [--name <env-name>]
::  - To install for regular conda, call with argument: --conda default
::  - To specify a different environment name, call with argument: --name <env-name>
::
:: Use the optional -e argument (in first position) to install in editable mode. In that case, any
:: change in the source code will be immediately reflected at execution, and the source folder
:: must not be moved or deleted after installation.


@echo off
setlocal EnableDelayedExpansion

set "MIRA_CMD_RUNNER_DIR=%ProgramFiles%\Mira Geoscience\Geoscience ANALYST\CmdRunner"
set curdir=%~dp0

pushd "%curdir%"
if not exist ".pixi" mkdir ".pixi"
set "MY_CONDA_ENV_FILE=%curdir%.pixi\analyst-environment.yml"
pixi exec --spec pixi=0.84.2 -- pixi workspace export conda-environment --from-lock-file --platform win-64 --environment runtime "%MY_CONDA_ENV_FILE%"
if errorlevel 1 (
  popd
  pause
  exit /B 1
)

set EXTRA_PIP_INSTALL_OPTIONS=

:: if provided and first arg equals "-e", install with pip editable mode
if /I "%~1" == "-e" (
  set "EXTRA_PIP_INSTALL_OPTIONS=-e"
  shift
)

"%MIRA_CMD_RUNNER_DIR%\MambaEnvRunner.exe" --name grid-apps --install "%MY_CONDA_ENV_FILE%" --with-pip-deps ^
   --run "pip install --no-deps -U --force-reinstall !EXTRA_PIP_INSTALL_OPTIONS! ." %1 %2 %3 %4 %5 %6 %7 %8 %9

set "INSTALL_EXIT_CODE=!errorlevel!"
popd
pause
exit /B %INSTALL_EXIT_CODE%

@echo off
setlocal
set "project_dir=%~dp0.."
pushd "%project_dir%"
pixi run --frozen pylint %*
set "exit_code=%errorlevel%"
popd
exit /B %exit_code%

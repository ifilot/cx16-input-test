@echo off
setlocal
rem Build with the WSL toolchain, then run the emulator natively.
rem Set X16INPUT_SKIP_BUILD=1 to launch the already-built program.
if "%X16INPUT_SKIP_BUILD%"=="1" goto find_emulator
where wsl.exe >nul 2>nul
if errorlevel 1 (
    echo WSL is required to build. Build with make first and set X16INPUT_SKIP_BUILD=1.
    goto failed
)
wsl.exe --cd "%~dp0." --exec make
if errorlevel 1 goto failed

:find_emulator
if not defined X16_EMU set "X16_EMU=%~dp0..\emulator\x16emu.exe"
if not exist "%X16_EMU%" (
    echo Windows emulator not found: "%X16_EMU%". Set X16_EMU to an x16emu.exe path.
    goto failed
)
if not defined X16_ROM set "X16_ROM=%~dp0..\emulator\rom.bin"
if not exist "%X16_ROM%" (
    echo ROM not found: "%X16_ROM%". Set X16_ROM to your rom.bin path.
    goto failed
)
pushd "%~dp0build"
if not exist X16INPUT.PRG (
    echo X16INPUT.PRG is missing. Build with make first.
    popd
    goto failed
)
"%X16_EMU%" -rom "%X16_ROM%" -prg X16INPUT.PRG -run -scale 2 %*
set "LAUNCH_RESULT=%ERRORLEVEL%"
popd
if not "%LAUNCH_RESULT%"=="0" goto failed
exit /b 0

:failed
echo Launch failed.
pause
exit /b 1

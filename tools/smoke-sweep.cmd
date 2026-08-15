@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem Sweep ONE smoke cvar across several values in the lab, one frame each.
rem
rem   smoke-sweep.cmd rt_smoke_ambient 0.08 0.3 0.6 1.0
rem
rem Every run is otherwise identical -- same map, same seed cadence, same tic for
rem the screenshot -- so the frames differ only by the swept value and can be put
rem side by side. That is the whole point: three rounds of this feature were
rem tuned against remembered impressions of different rooms.
rem
rem Frames land in tools\_smokelab\sweep-<cvar>\<value>.png
rem ---------------------------------------------------------------------------

set "HERE=%~dp0"
set "CVAR=%~1"
if "%CVAR%"=="" (
  echo Usage: %~nx0 ^<cvar^> ^<value^> [value ...]
  exit /b 1
)
shift

set "OUT=%HERE%_smokelab\sweep-%CVAR%"
if exist "%OUT%" rd /s /q "%OUT%"
mkdir "%OUT%"

:loop
if "%~1"=="" goto done
set "V=%~1"
echo === %CVAR% = %V% ===
rem A fixed capture tic, not a burst: comparing a sweep needs the SAME moment in
rem the plume's life in every frame, or parcel age becomes a second variable.
call "%HERE%smoke-lab.cmd" 1 -- +%CVAR% %V% +rt_autoshot 95 +rt_autoshot_every 0 +rt_autoquit 115 >nul 2>&1
for /f "delims=" %%D in ('dir /b /ad /o-d "%HERE%_smokelab\2026*" 2^>nul') do (
  for /f "delims=" %%F in ('dir /b "%HERE%_smokelab\%%D\*.png" 2^>nul') do (
    copy /y "%HERE%_smokelab\%%D\%%F" "%OUT%\%V%.png" >nul
    goto :got
  )
  goto :got
)
:got
rd /s /q "%HERE%_smokelab\2026*" 2>nul
for /f "delims=" %%D in ('dir /b /ad "%HERE%_smokelab\2026*" 2^>nul') do rd /s /q "%HERE%_smokelab\%%D"
shift
goto loop

:done
echo.
echo === sweep complete: %OUT% ===
dir /b "%OUT%"
exit /b 0

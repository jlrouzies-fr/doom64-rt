@echo off
setlocal EnableExtensions
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 (
  echo VsDevCmd failed
  exit /b 1
)

set "RTGL=G:\AI\Doom64-RT\deps\RTGL"
set "DLSS_SDK_PATH=G:\AI\Doom64-RT\deps\DLSS"
set "OUT=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"

if not exist "%DLSS_SDK_PATH%\include\nvsdk_ngx.h" (
  echo ERROR: DLSS SDK missing at %DLSS_SDK_PATH%
  echo Clone: git clone https://github.com/NVIDIA/DLSS "%DLSS_SDK_PATH%"
  exit /b 1
)
if not exist "%RTGL%\Include\RTGL1\RTGL1.h" (
  echo ERROR: RTGL missing at %RTGL%
  exit /b 1
)

echo DLSS_SDK_PATH=%DLSS_SDK_PATH%
echo === Generating shaders ===
pushd "%RTGL%\Source\Shaders"
rem GenerateShaders.py exits 0 even when glslangValidator rejects a shader, so
rem errorlevel alone is not enough -- a compile error would otherwise sail
rem through to BUILD_OK and get playtested against the previous SPV.
set "SHADERLOG=%TEMP%\shadergen.log"
python GenerateShaders.py -g > "%SHADERLOG%" 2>&1
set "SHADERGEN_RC=%errorlevel%"
type "%SHADERLOG%"
if not "%SHADERGEN_RC%"=="0" (
  echo Shader generation failed ^(exit %SHADERGEN_RC%^)
  popd
  exit /b 1
)
findstr /i /c:"error:" "%SHADERLOG%" >nul
if not errorlevel 1 (
  echo.
  echo ERROR: a shader failed to compile ^(see 'error:' lines above^).
  echo        Aborting so the OLD spv is not silently playtested.
  popd
  exit /b 1
)
popd

echo === Configuring RTGL ===
cmake -A x64 -S "%RTGL%" -B "%RTGL%\BuildCMake" ^
  -DCMAKE_BUILD_TYPE=RelWithDebInfo ^
  -DRG_WITH_SURFACE_WIN32=ON ^
  -DRG_WITH_NATIVE_DLSS=ON ^
  -DRG_WITH_EXAMPLES=OFF
if errorlevel 1 exit /b 1

echo === Building RTGL RelWithDebInfo ===
cmake --build "%RTGL%\BuildCMake" --config RelWithDebInfo --parallel
if errorlevel 1 exit /b 1

echo === Staging into gzdoom RelWithDebInfo ===
if not exist "%OUT%\rt\bin" mkdir "%OUT%\rt\bin"
if not exist "%OUT%\rt\shaders" mkdir "%OUT%\rt\shaders"

rem The DLL is LOCKED while gzdoom is running, and `copy` failing here is
rem SILENT: the script still reaches BUILD_OK, so fresh shaders get playtested
rem against a stale DLL. That exact trap is documented in compat-patches.md and
rem it bit again on 2026-08-10. Check the copy.
copy /Y "%RTGL%\Build\bin\RTGL1.dll" "%OUT%\rt\bin\" >nul
if errorlevel 1 (
  echo ERROR: could not stage RTGL1.dll -- is gzdoom.exe still running?
  echo        The BUILD succeeded but the engine tree still holds the OLD dll.
  exit /b 1
)
if exist "%RTGL%\Build\bin\RTGL1.pdb" copy /Y "%RTGL%\Build\bin\RTGL1.pdb" "%OUT%\rt\bin\" >nul

rem Prefer release NGX snippets from SDK (includes Ray Reconstruction)
copy /Y "%DLSS_SDK_PATH%\lib\Windows_x86_64\rel\nvngx_dlss.dll" "%OUT%\rt\bin\" >nul
copy /Y "%DLSS_SDK_PATH%\lib\Windows_x86_64\rel\nvngx_dlssd.dll" "%OUT%\rt\bin\" >nul

rem Updated compute shaders used by rebuilt RTGL1.dll
xcopy /Y /Q "%RTGL%\Build\shaders\*.spv" "%OUT%\rt\shaders\" >nul

echo BUILD_OK %OUT%\rt\bin\RTGL1.dll
dir "%OUT%\rt\bin\RTGL1.dll"
dir "%OUT%\rt\bin\nvngx_dlssd.dll"
exit /b 0

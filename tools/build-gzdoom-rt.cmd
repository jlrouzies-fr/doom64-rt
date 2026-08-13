@echo off
setlocal EnableExtensions
rem Project root, derived from this script's own location, so a clone can live
rem anywhere. Nothing below may hardcode an absolute path into the repo.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 (
  echo VsDevCmd failed
  exit /b 1
)

rem All project SDKs live under %PROJ%\deps (never Program Files)
rem Matching fork for gzdoom-rt (sultim-t/RayTracedGL1 doom/hl1 branches are too old)
set "RTGL1_SDK_PATH=%PROJ%\deps\RTGL"
if not exist "%RTGL1_SDK_PATH%\Include\RTGL1\RTGL1.h" (
  echo ERROR: RTGL1 headers missing at %RTGL1_SDK_PATH%\Include
  echo Clone https://github.com/vs-shirokii/RTGL into %PROJ%\deps\RTGL
  exit /b 1
)
echo RTGL1_SDK_PATH=%RTGL1_SDK_PATH%

set "ROOT=%PROJ%\sourcecode\gzdoom-rt"
if not exist "%ROOT%\build" mkdir "%ROOT%\build"
cd /d "%ROOT%\build"

if not exist vcpkg git clone https://github.com/microsoft/vcpkg
if not exist zmusic git clone https://github.com/zdoom/zmusic

mkdir "%ROOT%\build\zmusic\build" 2>nul
mkdir "%ROOT%\build\vcpkg_installed" 2>nul

echo === Building ZMusic (no libsndfile/yasm) ===
cmake -A x64 -S ./zmusic -B ./zmusic/build ^
	-DCMAKE_TOOLCHAIN_FILE=../vcpkg/scripts/buildsystems/vcpkg.cmake ^
	-DVCPKG_LIBSNDFILE=0 ^
	-DVCPKG_INSTALLLED_DIR=../vcpkg_installed/
if errorlevel 1 exit /b 1
cmake --build ./zmusic/build --config Release -- -maxcpucount -verbosity:minimal
if errorlevel 1 exit /b 1

echo === Configuring GZDoom-RT ===
cmake -A x64 -S .. -B . ^
	-DCMAKE_TOOLCHAIN_FILE=./vcpkg/scripts/buildsystems/vcpkg.cmake ^
	-DZMUSIC_INCLUDE_DIR=./zmusic/include ^
	-DZMUSIC_LIBRARIES=./zmusic/build/source/Release/zmusic.lib ^
	-DVCPKG_INSTALLLED_DIR=./vcpkg_installed/ ^
	-DHAVE_RT=ON
if errorlevel 1 exit /b 1

echo === Building GZDoom-RT RelWithDebInfo ===
cmake --build . --config RelWithDebInfo -- -maxcpucount -verbosity:minimal
set EC=%ERRORLEVEL%
echo EXITCODE=%EC%
if %EC% neq 0 exit /b %EC%

echo === Staging runtime from release package ===
set "OUT=%ROOT%\build\RelWithDebInfo"
set "REL=%PROJ%\gzdoom-rt-1.0.2"
if not exist "%OUT%\rt" xcopy /E /I /Y "%REL%\rt" "%OUT%\rt"
copy /Y "%REL%\libsndfile-1.dll" "%OUT%\" >nul
copy /Y "%REL%\openal32.dll" "%OUT%\" >nul
copy /Y "%ROOT%\build\zmusic\build\source\Release\zmusic.dll" "%OUT%\" >nul 2>nul
if not exist "%OUT%\zmusic.dll" copy /Y "%REL%\zmusic.dll" "%OUT%\" >nul

rem ---------------------------------------------------------------------------
rem Everything below used to be three manual first-run steps, and each of them
rem fails SILENTLY when skipped. They are cheap, they are idempotent, and they
rem have to re-run after any clean build, because the block above restages
rem %OUT%\rt wholesale from the stock package. No Python: a user who only wants
rem to play should not need an interpreter.
rem ---------------------------------------------------------------------------

rem 1. RTGL1 only ever READS RTGL1.json (VulkanDevice_Init.cpp, .value_or). No
rem    file means developerMode=false, which means every authored PNG material is
rem    ignored and the game quietly looks stock.
if not exist "%OUT%\rt\RTGL1.json" (
  echo === Writing rt\RTGL1.json ^(developerMode on^) ===
  >  "%OUT%\rt\RTGL1.json" echo {
  >> "%OUT%\rt\RTGL1.json" echo   "version": 0,
  >> "%OUT%\rt\RTGL1.json" echo   "developerMode": true,
  >> "%OUT%\rt\RTGL1.json" echo   "vulkanValidation": false,
  >> "%OUT%\rt\RTGL1.json" echo   "dx12Validation": false,
  >> "%OUT%\rt\RTGL1.json" echo   "dlssValidation": false,
  >> "%OUT%\rt\RTGL1.json" echo   "fpsMonitor": false
  >> "%OUT%\rt\RTGL1.json" echo }
)

rem 2. The authored RT materials. The generators write both trees, so this only
rem    matters on a fresh checkout or after the restage above.
if exist "%PROJ%\Doom64-Retribution\Retribution-RT-Materials\rt" (
  echo === Staging authored RT materials ===
  xcopy /E /I /Y /Q "%PROJ%\Doom64-Retribution\Retribution-RT-Materials\rt" "%OUT%\rt" >nul
)

rem 3. The menu overlay. rt\wad is appended AFTER every -file PWAD, so without
rem    this the stock RT menu art wins over Retribution's.
if exist "%PROJ%\rt-wad-overlay" (
  echo === Syncing rt-wad-overlay into rt\wad ===
  xcopy /E /I /Y /Q "%PROJ%\rt-wad-overlay" "%OUT%\rt\wad" >nul
)

echo BUILD_OK %OUT%\gzdoom.exe
dir "%OUT%\gzdoom.exe"
exit /b 0

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

rem The C and GLSL halves of ShGlobalUniform are generated from one list but
rem packed by different rules, and a scalar run that is not a multiple of four
rem silently moves every vec4 after it in GLSL only. Nothing reports that: the
rem shader simply reads the wrong addresses. It has cost two sessions here, so
rem the build refuses to continue.
echo === Checking ShGlobalUniform layout ===
python "%~dp0check_uniform_layout.py"
if errorlevel 1 (
  echo.
  echo Refusing to build against a uniform whose two layouts disagree.
  exit /b 1
)

rem ---------------------------------------------------------------------------
rem THE GENERATED HEADER IS NOT A TRACKED DEPENDENCY, and that cost a full day.
rem
rem GenerateShaders.py -g rewrites Source/Generated/ShaderCommonC.h, which defines
rem struct ShGlobalUniform. CMake/MSBuild do not know every .cpp depends on it, so
rem a file that was not otherwise edited KEEPS ITS STALE OBJECT. GlobalUniform.cpp
rem is the one that matters: it allocates the uniform buffer with
rem sizeof(ShGlobalUniform). When the struct grew for localised smoke, that .obj
rem was hours old and still allocated the OLD size -- so the buffer was 1984 bytes
rem while the rest of the library wrote and read 3024.
rem
rem The symptom is the worst kind: every field BELOW the old size works perfectly
rem and every field above it silently reads ZERO. No validation error, no crash,
rem nothing in any log. It looks exactly like a shader that ignores its input, and
rem it was chased through the API, the pNext chain, std140 offsets and the SPIR-V
rem before the timestamps gave it away.
rem
rem So: if the generated header changed, throw the objects away.
set "GENHDR=%RTGL%\Source\Generated\ShaderCommonC.h"
set "GENSTAMP=%RTGL%\BuildCMake\ShaderCommonC.stamp"
set "GENCHANGED="
if not exist "%GENSTAMP%" (
  set "GENCHANGED=1"
) else (
  fc /b "%GENHDR%" "%GENSTAMP%" >nul 2>&1
  if errorlevel 1 set "GENCHANGED=1"
)
if defined GENCHANGED (
  echo === ShaderCommonC.h changed -- clearing objects so nothing keeps a stale ^
struct layout ===
  if exist "%RTGL%\BuildCMake\RayTracedGL1.dir" rd /s /q "%RTGL%\BuildCMake\RayTracedGL1.dir"
)

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

rem Record the header we just built against, so the next run can tell.
if not exist "%RTGL%\BuildCMake" mkdir "%RTGL%\BuildCMake"
copy /y "%GENHDR%" "%GENSTAMP%" >nul

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

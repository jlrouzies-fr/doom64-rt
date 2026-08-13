@echo off
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem ---------------------------------------------------------------------------
rem Build an OLD RTGL commit into tools\rtgl-variants\<name>\ so it can be A/B'd
rem against the current build with ab-rtgl-baseline.cmd, without disturbing the
rem deps\RTGL working tree (a git worktree is used, then removed).
rem
rem Both the DLL and its SPIR-V are captured, because the ShGlobalUniform layout
rem has changed repeatedly -- mixing a DLL with another commit's shaders reads
rem every uniform at the wrong offset.
rem
rem Usage: build-rtgl-variant.cmd <commit-ish> <name>
rem   e.g. build-rtgl-variant.cmd d50bbcb aug05
rem ---------------------------------------------------------------------------

set "REF=%~1"
set "NAME=%~2"
if "%REF%"=="" goto :usage
if "%NAME%"=="" goto :usage

call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 1

set "RTGL=%PROJ%\deps\RTGL"
set "WT=%PROJ%\deps\RTGL-bisect"
set "DLSS_SDK_PATH=%PROJ%\deps\DLSS"
set "DEST=%PROJ%\tools\rtgl-variants\%NAME%"

rem A stale worktree from an interrupted run would silently build the wrong commit.
if exist "%WT%" (
  git -C "%RTGL%" worktree remove --force "%WT%" 2>nul
  if exist "%WT%" rmdir /S /Q "%WT%"
)

git -C "%RTGL%" worktree add --detach "%WT%" %REF%
if errorlevel 1 exit /b 1

echo === %NAME%: building RTGL at %REF% ===
git -C "%WT%" log -1 --format="%%h %%ad %%s" --date=short

rem A worktree does not get the submodule working trees, and CMake needs them
rem (glfw/glaze/imgui/... are add_subdirectory'd). Copy the live checkouts rather
rem than re-initialising: these are third-party pins that did not move during the
rem window being bisected, so they are not part of what is under test.
for %%S in (imgui glfw cgltf glaze glm DX12) do (
  if exist "%RTGL%\Source\%%S\" (
    robocopy "%RTGL%\Source\%%S" "%WT%\Source\%%S" /E /NFL /NDL /NJH /NJS /NP >nul
  )
)

pushd "%WT%\Source\Shaders"
python GenerateShaders.py -g
if errorlevel 1 ( popd & goto :fail )
popd

cmake -A x64 -S "%WT%" -B "%WT%\BuildCMake" ^
  -DCMAKE_BUILD_TYPE=RelWithDebInfo ^
  -DRG_WITH_SURFACE_WIN32=ON ^
  -DRG_WITH_NATIVE_DLSS=ON ^
  -DRG_WITH_EXAMPLES=OFF
if errorlevel 1 goto :fail

cmake --build "%WT%\BuildCMake" --config RelWithDebInfo --parallel
if errorlevel 1 goto :fail

if not exist "%DEST%\shaders" mkdir "%DEST%\shaders"
copy /Y "%WT%\Build\bin\RTGL1.dll" "%DEST%\RTGL1.dll" >nul
if errorlevel 1 goto :fail
xcopy /Y /Q "%WT%\Build\shaders\*.spv" "%DEST%\shaders\" >nul
if errorlevel 1 goto :fail

rem RR must be compiled IN, or the variant silently falls back to A-SVGF and a
rem clean image would be meaningless. This is root cause #1 from 2026-08-06.
findstr /C:"NVSDK_NGX_VULKAN_EvaluateFeature" "%DEST%\RTGL1.dll" >nul
if errorlevel 1 (
  echo ERROR: %NAME% has NO Ray Reconstruction compiled in - variant is unusable
  goto :fail
)

git -C "%RTGL%" worktree remove --force "%WT%"
echo VARIANT_OK %DEST%
exit /b 0

:fail
git -C "%RTGL%" worktree remove --force "%WT%" 2>nul
echo VARIANT_FAILED %NAME%
exit /b 1

:usage
echo Usage: %~nx0 ^<commit-ish^> ^<name^>
exit /b 1

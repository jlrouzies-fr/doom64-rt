@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the A-SVGF antilag gate on INDIRECT ReSTIR temporal reuse.
rem
rem RtRaygenIndirect rejects a temporal reuse tap when
rem   framebufDISGradientHistory[pp / STRATA][1] > 0.25
rem That buffer is written ONLY by CmASVGFGradientAtrous, which runs only inside
rem Denoiser::Denoise(). DLSS-RR skips Denoise() entirely and calls ComposeNoisy()
rem instead -- so under RR the gate tests a buffer that nothing ever updates.
rem
rem Either it is a dead no-op, or it rejects GI temporal reuse every frame. The
rem second would leave indirect lighting at 1 spp with no accumulation at all:
rem surfaces fizzle, only the denoiser's own history hides it, and motion removes
rem exactly that. It would also explain why rt_spp_* barely helps -- more samples
rem per frame cannot substitute for lost temporal accumulation.
rem
rem This fits what is already measured:
rem   - direct reservoir M stays high in motion  -> sampling/light selection fine
rem   - 8 spp buys only ~20%                     -> not Monte Carlo variance
rem   - InReset flush on/off: no difference      -> not history flushing
rem   - disocclusion mask: sparse in motion      -> not the mask
rem
rem   1 = apply the gate (stock)
rem   0 = ignore it (GI temporal reuse always allowed)
rem
rem Confirm the arm took: rt-console.log prints
rem   ReSTIR uniforms: ... indirAntilagGate=on|off
rem
rem JUDGE IN MOTION. The whole hypothesis is about temporal accumulation, so a
rem static comparison cannot show it -- that mistake already produced one false
rem null this session (rt_restir_bluenoise, judged in the unfiltered view).
rem
rem Usage: ab-indir-antilag.cmd <0|1> [1-32]
rem ---------------------------------------------------------------------------

set "MODE=%~1"
set "MAP=%~2"
if "%MODE%"=="" set "MODE=0"
if "%MAP%"==""  set "MAP=2"

if not "%MODE%"=="0" if not "%MODE%"=="1" (
  echo Usage: %~nx0 ^<0^|1^> [1-32]
  exit /b 1
)

echo === rt_restir_indir_antilag %MODE%, MAP%MAP% ===
echo     walk around and compare motion stability, not a static frame
call "%~dp0launch-retribution-rt.cmd" %MAP% -- +rt_restir_indir_antilag %MODE%
exit /b %ERRORLEVEL%

// Doom64-RT: hand-written equivalent of the file NRD's CMake generates
// (CMakeLists.txt:77-88), since we drive ShaderMake directly like Duke-RT does.
// MUST match the NRD_* compile definitions the C++ side is built with
// (deps/RTGL build wiring) -- a mismatch is a silent contract break between
// the shaders and InstanceImpl.
//
// Values are Duke-RT's proven configuration (Duke-RT source/CMakeLists.txt)
// with ONE deliberate divergence: NRD_SUPPORTS_ANTIFIREFLY=1, because this
// game's 1-spp ReSTIR signal genuinely produces fireflies (A-SVGF ships an
// anti-firefly pass) and compiling support in makes enableAntiFirefly a
// runtime A/B knob instead of a shader regeneration.
#define NRD_NORMAL_ENCODING 2
#define NRD_ROUGHNESS_ENCODING 1
#define NRD_SUPPORTS_VIEWPORT_OFFSET 0
#define NRD_SUPPORTS_CHECKERBOARD 0
#define NRD_SUPPORTS_HISTORY_CONFIDENCE 0
#define NRD_SUPPORTS_DISOCCLUSION_THRESHOLD_MIX 0
#define NRD_SUPPORTS_BASECOLOR_METALNESS 1
#define NRD_SUPPORTS_ANTIFIREFLY 1
#define REBLUR_PERFORMANCE_MODE 0

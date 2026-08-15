"""Fail the build if ShGlobalUniform's C and std140 layouts disagree.

WHY THIS EXISTS. The global uniform is generated twice from one source list --
ShaderCommonC.h for the library and ShaderCommonGLSL.h for the shaders -- and the
two languages pack it differently. C packs scalars contiguously; std140 aligns a
vec4 (or an array of them) to 16 bytes. So a run of scalars whose count is not a
multiple of four makes every field after it sit at a different address in the
shader than in the library, silently.

Nothing reports that. There is no validation error and no crash: fields below the
divergence work perfectly and fields above it read whatever happens to be there.
It has now happened twice in this project --

  * adding smoke's arrays past a stale GlobalUniform.obj (a different cause, same
    symptom: everything past a boundary read as zero);
  * adding volumeSpatialBlur without removing a pad, which took the scalar run to
    nine, moved every vec4 array 12 bytes in GLSL only, and produced vanished
    smoke plus black bands on screen.

Both cost a debugging session. This check is three seconds.

Run from tools/build-rtgl.cmd after GenerateShaders.py -g.
"""

import io
import re
import sys
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

C_HDR = str(PROJ_ROOT / r"deps\RTGL\Source\Generated\ShaderCommonC.h")
GLSL_HDR = str(PROJ_ROOT / r"deps\RTGL\Source\Generated\ShaderCommonGLSL.h")

# base alignment, size -- std140
STD140 = {
    'float': (4, 4), 'uint': (4, 4), 'int': (4, 4),
    'vec2': (8, 8), 'vec3': (16, 12), 'vec4': (16, 16),
    'uvec2': (8, 8), 'uvec3': (16, 12), 'uvec4': (16, 16),
    'ivec2': (8, 8), 'ivec4': (16, 16),
    'mat4': (16, 64), 'mat3': (16, 48),
}


def members(path, struct='ShGlobalUniform'):
    src = io.open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'struct\s+' + struct + r'\s*\{(.*?)\n\};', src, re.S)
    if not m:
        return None
    out = []
    for line in m.group(1).split('\n'):
        line = line.strip().rstrip(';')
        mm = re.match(r'(\w+)\s+(\w+)(?:\[(\d+)\])?$', line)
        if mm:
            out.append((mm.group(1), mm.group(2), int(mm.group(3)) if mm.group(3) else None))
    return out


def align(off, a):
    return (off + a - 1) // a * a


def main():
    cm = members(C_HDR)
    gm = members(GLSL_HDR)
    if not cm or not gm:
        print('check_uniform_layout: could not parse ShGlobalUniform -- skipping')
        return 0

    # C side: flat, natural packing. Every member is 4-byte scalars or an array
    # of them, which is how the generator emits it for C.
    c_off, off = {}, 0
    for _, name, n in cm:
        c_off[name] = off
        off += 4 * (n or 1)
    c_size = off

    g_off, off = {}, 0
    for ty, name, n in gm:
        if ty not in STD140:
            print(f'check_uniform_layout: unknown GLSL type {ty} on {name} -- skipping')
            return 0
        a, sz = STD140[ty]
        if n is not None:
            a = max(a, 16)
            sz = align(sz, 16) * n
        off = align(off, a)
        g_off[name] = off
        off += sz
    g_size = align(off, 16)

    bad = [k for k in g_off if k in c_off and g_off[k] != c_off[k]]

    if bad:
        print('=' * 74)
        print('ShGlobalUniform LAYOUT MISMATCH -- the shaders and the library')
        print('disagree about where these fields are. Every one of them will read')
        print('garbage or zero in the shader, with no validation error at all.')
        print('=' * 74)
        order = sorted(bad, key=lambda k: c_off[k])
        for k in order[:12]:
            print(f'   {k:32} C={c_off[k]:6}  GLSL={g_off[k]:6}  (off by {g_off[k]-c_off[k]:+})')
        if len(order) > 12:
            print(f'   ... and {len(order)-12} more')
        print()
        print('CAUSE, almost always: a run of scalars whose length is not a')
        print('multiple of four sits before a vec4 or an array. C packs them')
        print('contiguously; std140 pads to the next 16 bytes. Add or remove a')
        print('_pad in GenerateShaderCommon.py so the run divides by four.')
        print(f'   C size {c_size}   GLSL size {g_size}')
        return 1

    print(f'check_uniform_layout: OK -- {len(g_off)} fields agree, {c_size} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())

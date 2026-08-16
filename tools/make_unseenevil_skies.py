"""Bake Unseen Evil's shader-driven skies into real textures, for the RT renderer.

THE PROBLEM. Unseen Evil's Terraformer swaps every map's sky to one of
textures/d64/skybox_{c,wind,city,fire} (level.ChangeSky, per cluster). TEXTURES.skies
defines all of those as 32x32 STUBS holding a single patch -- the sky you actually
see in GZDoom is produced entirely by shaders/d64ue/sky_3d.fp, from a 3-colour ramp,
a cloud tile and a mountain silhouette.

RTGL1 draws the sky itself and never runs GZDoom's custom fragment shaders, so under
RT the stub is all there is, and the sky renders as a flat blank. This bakes what the
shader would have produced into an ordinary 256x128 sky texture that RT can draw.

WHAT IT REPRODUCES, and where each step comes from in sky_3d.fp:

    baseColor = tex_colors(0.1)   highColor = tex_colors(0.4)   lowColor = tex_colors(0.8)

    cloudTex  = CLOUD * baseColor * 0.56, faded in by clamp(skyPos.y*3, 0, 1)
    cloudTex += mix(lowColor, highColor, skyPos.y)
    result    = mix(cloudTex, mountTex, mountTex.a)

so: a vertical gradient running lowColor at the horizon -> highColor at the zenith,
clouds tinted by baseColor and fading out as they approach the horizon, and the
mountain silhouette composited over by its own alpha.

WHAT IT CANNOT REPRODUCE, deliberately: the shader scrolls its cloud UVs by `timer`
(two layers, opposite directions) and the fire sky is procedural. A baked texture is
static. That is a real loss and it is the correct trade -- a still sky that looks like
the mod beats a moving sky that does not exist.

The mountain placement is NOT invented: the mod's own TEXTURES.skies composites
SKY1 = SPACE + MOUNTA at y=48 and SKY2 = SPACE + MOUNTB at y=32, both bottom-aligned
in a 256x128 texture, and that alignment is reused here.

    py -3 tools/make_unseenevil_skies.py            # census: report, write nothing
    py -3 tools/make_unseenevil_skies.py --write    # build the overlay pk3
"""

import argparse
import io
import zipfile
from pathlib import Path

from PIL import Image

PROJ = Path(__file__).resolve().parent.parent
MOD = PROJ / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
OUT = PROJ / "Doom64-UnseenEvil" / "d64ue-sky-rt.pk3"

W, H = 256, 128
CLOUD_MULT = 0.56  # sky_3d.fp: cloudTex *= vec4(0.56, 0.56, 0.56, 1.0)

# name -> (colour ramp, horizon art, y offset of that art)
# The y offsets are the mod's own, from its SKY1/SKY2 composites.
SKIES = {
    "c":    ("resources/skies/d64_skycolors_c.png",    "textures/d64/sky/MOUNTB.png",        32),
    "wind": ("resources/skies/d64_skycolors_wind.png", "textures/d64/sky/MOUNTA.png",        48),
    "city": ("resources/skies/d64_skycolors_city.png", "textures/pepy/skies/d64_city_skyline.png", 32),
}


def _read(z, name):
    return Image.open(io.BytesIO(z.read(name)))


def bake(z, ramp_name, mount_name, mount_y):
    """One sky, following sky_3d.fp's Process() top to bottom."""
    ramp = _read(z, ramp_name).convert("RGB")
    base = ramp.getpixel((0, 0))               # tex_colors(0.1)
    high = ramp.getpixel((min(1, ramp.width - 1), 0))  # tex_colors(0.4)
    low = ramp.getpixel((min(2, ramp.width - 1), 0))   # tex_colors(0.8)

    cloud = _read(z, "graphics/CLOUD.png").convert("RGB")

    sky = Image.new("RGB", (W, H))
    px = sky.load()
    cw, ch = cloud.size
    cpx = cloud.load()

    for y in range(H):
        # v=0 is the top of a Doom sky texture, i.e. the zenith. skyPos.y runs the
        # other way, 1 at the zenith and 0 at the horizon.
        sky_y = 1.0 - (y / (H - 1))

        # mix(lowColor, highColor, skyPos.y)
        gr = low[0] + (high[0] - low[0]) * sky_y
        gg = low[1] + (high[1] - low[1]) * sky_y
        gb = low[2] + (high[2] - low[2]) * sky_y

        # clouds fade out toward the horizon
        fade = min(1.0, max(0.0, sky_y * 3.0))

        for x in range(W):
            c = cpx[(x * 2) % cw, (y * 2) % ch]
            r = gr + c[0] / 255.0 * base[0] * CLOUD_MULT * fade
            g = gg + c[1] / 255.0 * base[1] * CLOUD_MULT * fade
            b = gb + c[2] / 255.0 * base[2] * CLOUD_MULT * fade
            px[x, y] = (min(255, int(r)), min(255, int(g)), min(255, int(b)))

    mount = _read(z, mount_name).convert("RGBA")
    if mount.width != W:
        mount = mount.resize((W, mount.height), Image.NEAREST)
    sky_rgba = sky.convert("RGBA")
    sky_rgba.alpha_composite(mount, (0, mount_y))
    return sky_rgba.convert("RGB"), base, high, low


def bake_fire(z):
    """The fire sky has no cloud layer (ISFIRESKY) -- its whole look is tex_mount,
    which is the procedural skyfire. fire_noise.png is that shader's own input and
    is already 256x128, so it stands in directly."""
    return _read(z, "graphics/fire_noise.png").convert("RGB")


TEXTURES_LUMP = """// Doom64-RT: real sky textures for the RT renderer.
//
// Unseen Evil defines textures/d64/skybox_* as 32x32 stubs because its skies are
// drawn by shaders/d64ue/sky_3d.fp. RTGL1 never runs that shader, so under RT the
// stub is the whole sky and it renders blank. These redefinitions point the same
// names at baked 256x128 images (tools/make_unseenevil_skies.py) so there is
// something real to draw.
//
// Same names, later in the load order, so these win. Nothing is deleted: with this
// overlay absent the mod behaves exactly as it always has.

Texture "textures/d64/skybox_c", 256, 128 { Patch "textures/d64rt/sky_c.png", 0, 0 }
Texture "textures/d64/sky_c", 256, 128 { Patch "textures/d64rt/sky_c.png", 0, 0 }

Texture "textures/d64/skybox_wind", 256, 128 { Patch "textures/d64rt/sky_wind.png", 0, 0 }
Texture "textures/d64/sky_wind", 256, 128 { Patch "textures/d64rt/sky_wind.png", 0, 0 }

Texture "textures/d64/skybox_city", 256, 128 { Patch "textures/d64rt/sky_city.png", 0, 0 }
Texture "textures/d64/sky_city", 256, 128 { Patch "textures/d64rt/sky_city.png", 0, 0 }

Texture "textures/d64/skybox_fire", 256, 128 { Patch "textures/d64rt/sky_fire.png", 0, 0 }
Texture "textures/d64/sky_fire", 256, 128 { Patch "textures/d64rt/sky_fire.png", 0, 0 }
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="build the overlay pk3")
    args = ap.parse_args()

    if not MOD.exists():
        raise SystemExit(f"missing {MOD}")

    baked = {}
    with zipfile.ZipFile(MOD) as z:
        for name, (ramp, mount, y) in SKIES.items():
            img, base, high, low = bake(z, ramp, mount, y)
            baked[name] = img
            print(f"  sky_{name:5s} base={base} high={high} low={low}  "
                  f"horizon={Path(mount).name}@y{y}")
        baked["fire"] = bake_fire(z)
        print("  sky_fire  from graphics/fire_noise.png (ISFIRESKY: no cloud layer)")

    if not args.write:
        print("\ncensus only; pass --write to build", OUT.name)
        return

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("TEXTURES.d64rtskies", TEXTURES_LUMP)
        for name, img in baked.items():
            buf = io.BytesIO()
            img.save(buf, "PNG")
            # FULL PATH, not the patches/ namespace: a short patch name there did
            # not resolve ("Unknown patch 'd64rt_sky_c'") and the texture came out
            # blank white. The mod references its own patches by path for the same
            # reason, e.g. Patch "textures/pepy/d64_citybrick_blank.png".
            z.writestr(f"textures/d64rt/sky_{name}.png", buf.getvalue())
    print(f"\nwrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

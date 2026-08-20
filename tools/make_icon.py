"""Draw the Mitsubishi three-diamond mark.

Three slender rhombi (60 degrees at the inner and outer vertices, 120 at the
laterals) radiate from the centre at 120 degree intervals, their inner tips
meeting at the exact centre.  Because each diamond only occupies 60 degrees,
the three 60 degree gaps between them form the three-pointed star of negative
space the mark is known for.

Geometry is laid out in unit space, then scaled to fit the canvas from its
own bounding box so the artwork is centred whatever the size.
"""
import math
import pathlib
from PIL import Image, ImageDraw

RED = (230, 0, 18, 255)      # Mitsubishi red, #E60012
SS = 8                        # supersampling factor
INNER = 0.0                   # inner tips meet at the exact centre
PAD = 0.94                    # fraction of the canvas the mark fills


def diamond(axis_deg):
    """One rhombus in unit space, long axis radiating along axis_deg."""
    a = math.radians(axis_deg)
    ux, uy = math.cos(a), math.sin(a)        # along the axis
    px, py = -uy, ux                         # perpendicular
    length = 1.0 - INNER
    half_w = length / (2 * math.sqrt(3))     # gives 60 degree tips
    mid = INNER + length / 2
    return [
        (ux * INNER, uy * INNER),                              # inner tip
        (ux * mid + px * half_w, uy * mid + py * half_w),      # lateral
        (ux * 1.0, uy * 1.0),                                  # outer tip
        (ux * mid - px * half_w, uy * mid - py * half_w),      # lateral
    ]


def render(size, fill=RED):
    shapes = [diamond(axis) for axis in (90, 210, 330)]
    xs = [x for s in shapes for x, _ in s]
    ys = [y for s in shapes for _, y in s]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    scale = size * SS * PAD / span
    ox = (size * SS - (max(xs) - min(xs)) * scale) / 2 - min(xs) * scale
    oy = (size * SS - (max(ys) - min(ys)) * scale) / 2 - min(ys) * scale

    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for shape in shapes:
        # Negate y: image rows run downwards, so a diamond at 90 points up.
        draw.polygon(
            [(ox + x * scale, size * SS - (oy + y * scale)) for x, y in shape],
            fill=fill,
        )
    return img.resize((size, size), Image.LANCZOS)


OUT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "mitsubishi_msz" / "brand"

for name, size in (("icon.png", 256), ("icon@2x.png", 512),
                   ("logo.png", 256), ("logo@2x.png", 512)):
    OUT.mkdir(parents=True, exist_ok=True)
    render(size).save(OUT / name)
    print(f"wrote {OUT.name}/{name} ({size}x{size})")

"""Generate placeholder logos + an app icon, and convert sample .ovl profiles.

The original logo files shipped in the .rar were 0 bytes (empty), so we create
clean placeholder logos for the known clients so the app has usable defaults.
Any real logo files that DO contain data are copied as-is.
"""
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LOGOS = os.path.join(HERE, "resources", "logos")
PROFILES = os.path.join(HERE, "profiles")
SRC_LOGOS = "/home/ubuntu/Overlay_extracted/Overlay/Logo"
SRC_OVL = "/home/ubuntu/Overlay_extracted"
os.makedirs(LOGOS, exist_ok=True)
os.makedirs(PROFILES, exist_ok=True)


def _font(size):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_logo(filename, text, bg, fg, size=(360, 150)):
    img = Image.new("RGBA", size, bg + (255,))
    d = ImageDraw.Draw(img)
    f = _font(54)
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text(((size[0] - w) / 2 - bbox[0], (size[1] - h) / 2 - bbox[1]),
           text, font=f, fill=fg + (255,))
    d.rounded_rectangle([2, 2, size[0] - 3, size[1] - 3], radius=14,
                        outline=fg + (255,), width=3)
    out = os.path.join(LOGOS, filename)
    if filename.lower().endswith((".jpg", ".jpeg")):
        img.convert("RGB").save(out, quality=92)
    else:
        img.save(out)
    print("logo:", filename)


# Copy any non-empty real logos first
copied = set()
if os.path.isdir(SRC_LOGOS):
    for fn in os.listdir(SRC_LOGOS):
        s = os.path.join(SRC_LOGOS, fn)
        if os.path.isfile(s) and os.path.getsize(s) > 100 and fn.lower() != "thumbs.db":
            shutil.copy2(s, os.path.join(LOGOS, fn))
            copied.add(fn.lower())
            print("copied real logo:", fn)

# Placeholder logos for known clients (only if a real one wasn't copied)
placeholders = [
    ("bp_Logo.jpg", "BP", (0, 110, 60), (245, 230, 0)),
    ("Burullus_Logo.JPG", "BURULLUS", (0, 60, 120), (255, 255, 255)),
    ("DeepTech_Logo.jpg", "DEEPTECH", (10, 25, 60), (0, 170, 255)),
    ("DeepTech-PMS Logo.jpg", "DEEPTECH-PMS", (10, 25, 60), (0, 200, 180)),
    ("PhPC.jpg", "PhPC", (120, 0, 30), (255, 255, 255)),
    ("ROV - Combined.png", "ROV", (30, 30, 40), (255, 160, 0)),
]
for fn, text, bg, fg in placeholders:
    if fn.lower() not in copied:
        # save placeholders as PNG content regardless of extension
        make_logo(fn, text, bg, fg)


def make_icon():
    img = Image.new("RGBA", (256, 256), (26, 26, 46, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 20, 236, 236], radius=40, fill=(15, 52, 96, 255))
    f = _font(150)
    text = "R"
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    d.text(((256 - w) / 2 - bbox[0], (256 - h) / 2 - bbox[1]), text, font=f,
           fill=(233, 69, 96, 255))
    ico_path = os.path.join(HERE, "resources", "icon.ico")
    img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                              (128, 128), (256, 256)])
    print("icon:", ico_path)


make_icon()


def convert_profiles():
    import sys
    sys.path.insert(0, HERE)
    from app.ovl_io import import_ovl
    count = 0
    for root, _, files in os.walk(SRC_OVL):
        for fn in files:
            if fn.lower().endswith(".ovl"):
                try:
                    prof = import_ovl(os.path.join(root, fn))
                    out = os.path.join(PROFILES, prof.profile_name + ".json")
                    prof.save(out)
                    count += 1
                except Exception as exc:
                    print("skip", fn, exc)
    print(f"converted {count} profiles")


convert_profiles()

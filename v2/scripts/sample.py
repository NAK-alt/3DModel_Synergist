import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB"); w, h = im.size
for name, (x, y) in {"lit": (0.40, 0.46), "mid": (0.50, 0.62), "shade": (0.62, 0.60), "glove": (0.30, 0.41), "bg": (0.1, 0.1)}.items():
    print(name, im.getpixel((int(x * w), int(y * h))))

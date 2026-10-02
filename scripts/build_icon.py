"""Render packaging/icon.svg's geometry as a multi-size Windows ICO."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
size = 256
image = Image.new("RGBA", (size, size), "#080808")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((0, 0, 255, 255), radius=48, fill="#080808")
draw.polygon([(38,48),(90,48),(129,106),(167,48),(218,48),(203,208),(157,208),
              (165,120),(129,172),(92,120),(101,208),(53,208)], fill="#ff2d2d")
draw.polygon([(28,142),(233,93),(228,124),(31,171)], fill="#080808")
draw.polygon([(29,152),(226,105),(224,118),(28,165)], fill="#f4f1ed")
target = root / "packaging" / "mapa-roto.ico"
image.save(target, sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(target)


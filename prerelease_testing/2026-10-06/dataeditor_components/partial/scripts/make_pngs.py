"""Generate small distinctive PNG test images (pure stdlib)."""
import struct
import sys
import zlib
from pathlib import Path


def png(path: Path, w: int, h: int, fn) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw.extend(fn(x, y))
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(data)


def solid_with_stripes(c1, c2):
    return lambda x, y: c1 if (x // 16 + y // 16) % 2 == 0 else c2


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
png(out / "img_red.png", 160, 100, solid_with_stripes((220, 30, 30), (250, 200, 200)))
png(out / "img_a.png", 320, 200, solid_with_stripes((30, 90, 220), (200, 210, 250)))
png(out / "img_b.png", 200, 320, solid_with_stripes((30, 160, 60), (200, 240, 200)))
png(out / "img_c.png", 400, 120, solid_with_stripes((240, 160, 0), (255, 235, 180)))
if len(sys.argv) > 2:
    xo = Path(sys.argv[2])
    xo.mkdir(parents=True, exist_ok=True)
    png(xo / "xo_purple.png", 160, 160, solid_with_stripes((130, 40, 180), (230, 200, 245)))
print("ok")

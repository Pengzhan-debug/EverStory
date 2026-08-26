"""Build the lightweight README demo from the checked-in product screenshots."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets" / "readme"
OUTPUT = ASSETS / "everstory-demo.gif"
FRAMES = [
    ("gameplay-overview.png", "PLAY — STATE-CONSISTENT WORLD"),
    ("agent-team-chat.png", "DEBATE — AGENTS CHALLENGE HYPOTHESES"),
    ("case-evidence-board.png", "VERIFY — PLAYER-APPROVED EVIDENCE"),
    ("model-control-console.png", "ROUTE — PER-AGENT MODEL DIAGNOSTICS"),
]


def font(size: int):
    for path in ("C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build() -> None:
    output_frames = []
    for filename, label in FRAMES:
        image = Image.open(ASSETS / filename).convert("RGB")
        image = ImageOps.fit(image, (1280, 720), method=Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle((0, 0, 1280, 68), fill=(4, 15, 22, 226))
        draw.rectangle((0, 65, 1280, 68), fill=(210, 165, 75, 220))
        draw.text((34, 19), label, font=font(27), fill=(236, 217, 171, 255))
        output_frames.append(Image.alpha_composite(image.convert("RGBA"), overlay).convert("P", palette=Image.Palette.ADAPTIVE))
    output_frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=output_frames[1:],
        duration=[1800, 1800, 1800, 2200],
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()

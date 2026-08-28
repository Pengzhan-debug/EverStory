"""Build a lightweight cinematic README loop from real product captures."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets" / "readme"
OUTPUT = ASSETS / "everstory-demo.gif"
SCENES = [
    ("gameplay-overview.png", "01 / PLAY", "STATE-CONSISTENT AI WORLD"),
    ("agent-team-chat.png", "02 / DEBATE", "NAMED AGENTS CHALLENGE CLAIMS"),
    ("case-evidence-board.png", "03 / VERIFY", "PLAYER-APPROVED EVIDENCE"),
    ("model-control-console.png", "04 / ROUTE", "EMPIRICALLY SELECTED MODELS"),
]


def font(size: int):
    for path in ("C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_scene(image: Image.Image, chapter: str, label: str, progress: int, zoom: float) -> Image.Image:
    width, height = 1280, 720
    fitted = ImageOps.fit(image.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    if zoom > 1:
        zoomed = fitted.resize((round(width * zoom), round(height * zoom)), Image.Resampling.LANCZOS)
        left = (zoomed.width - width) // 2
        top = (zoomed.height - height) // 2
        fitted = zoomed.crop((left, top, left + width, top + height))

    overlay = Image.new("RGBA", fitted.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, width, 72), fill=(3, 13, 20, 224))
    draw.rectangle((0, 69, width, 72), fill=(211, 168, 76, 225))
    draw.text((34, 14), chapter, font=font(18), fill=(100, 222, 190, 255))
    draw.text((34, 37), label, font=font(24), fill=(242, 225, 184, 255))
    for index in range(len(SCENES)):
        x = width - 132 + index * 24
        fill = (211, 168, 76, 255) if index == progress else (105, 122, 130, 190)
        draw.ellipse((x, 29, x + 9, 38), fill=fill)
    return Image.alpha_composite(fitted.convert("RGBA"), overlay).convert("RGB")


def build() -> None:
    rendered: list[Image.Image] = []
    durations: list[int] = []
    scene_ends: list[Image.Image] = []
    for scene_index, (filename, chapter, label) in enumerate(SCENES):
        source = Image.open(ASSETS / filename)
        scene_frames = [
            render_scene(source, chapter, label, scene_index, 1 + step * 0.004)
            for step in range(5)
        ]
        if scene_ends:
            previous = scene_ends[-1]
            for fade_step in range(1, 4):
                rendered.append(Image.blend(previous, scene_frames[0], fade_step / 4))
                durations.append(100)
        rendered.extend(scene_frames)
        durations.extend([360, 360, 360, 360, 1000])
        scene_ends.append(scene_frames[-1])

    output_frames = [
        frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=96)
        for frame in rendered
    ]
    output_frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=output_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()

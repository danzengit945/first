"""
Build two small sample procedure PDFs, each with text, a table, and a diagram.

Run from this folder:
  python create_samples.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

OUT = Path(__file__).resolve().parent.parent / "procedures"


def _font(size: int):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_power_diagram(path: Path) -> None:
    image = Image.new("RGB", (900, 280), "white")
    draw = ImageDraw.Draw(image)
    font = _font(22)
    boxes = [
        (30, 90, 200, 180, "Solar Array"),
        (250, 90, 420, 180, "PCDU"),
        (470, 90, 640, 180, "Battery"),
        (690, 90, 870, 180, "Payload"),
    ]
    for x1, y1, x2, y2, label in boxes:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, outline="#1f4d38", width=4)
        draw.text((x1 + 16, y1 + 32), label, fill="#1a2e24", font=font)
    for start, end in ((200, 250), (420, 470), (640, 690)):
        draw.line((start, 135, end - 12, 135), fill="#8c3b2a", width=5)
        draw.polygon([(end - 12, 125), (end, 135), (end - 12, 145)], fill="#8c3b2a")
    image.save(path)


def draw_safe_diagram(path: Path) -> None:
    image = Image.new("RGB", (900, 280), "white")
    draw = ImageDraw.Draw(image)
    font = _font(22)
    boxes = [
        (40, 90, 250, 180, "Fault Detect"),
        (320, 90, 560, 180, "Safe Mode"),
        (630, 90, 860, 180, "Sun Point"),
    ]
    for x1, y1, x2, y2, label in boxes:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, outline="#1f4d38", width=4)
        draw.text((x1 + 18, y1 + 32), label, fill="#1a2e24", font=font)
    draw.line((250, 135, 308, 135), fill="#8c3b2a", width=5)
    draw.polygon([(308, 125), (320, 135), (308, 145)], fill="#8c3b2a")
    draw.line((560, 135, 618, 135), fill="#8c3b2a", width=5)
    draw.polygon([(618, 125), (630, 135), (618, 145)], fill="#8c3b2a")
    image.save(path)


def _table(data):
    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.12, 0.30, 0.22)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def build_power(diagram: Path, pdf: Path) -> None:
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SAT-PWR-001 Satellite Power-Up Procedure", styles["Title"]),
        Spacer(1, 0.15 * inch),
        Paragraph(
            "This procedure brings the training satellite from eclipse survival to payload power. "
            "Operators must confirm the power conditioning and distribution unit (PCDU) before closing the payload switch.",
            styles["BodyText"],
        ),
        Spacer(1, 0.15 * inch),
        Paragraph("Power path", styles["Heading2"]),
        RLImage(str(diagram), width=6.5 * inch, height=2.0 * inch),
        Spacer(1, 0.15 * inch),
        Paragraph(
            "The diagram shows Solar Array to PCDU to Battery to Payload. "
            "Do not connect the payload until the regulated bus is inside the limit below.",
            styles["BodyText"],
        ),
        Spacer(1, 0.15 * inch),
        Paragraph("Bus voltage limits", styles["Heading2"]),
        _table(
            [
                ["Check", "Limit", "Action if failed"],
                ["Regulated bus", "28.0 V +/- 0.5 V", "Stop. Open payload switch."],
                ["Battery", "Above 22.0 V", "Stay on solar array only."],
                ["Payload inrush", "Below 4.0 A", "Command payload off."],
            ]
        ),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "Step 4. When the regulated bus reads 28.0 V plus or minus 0.5 V, close the payload switch. "
            "Step 5. Confirm payload current stays below 4.0 A for 30 seconds.",
            styles["BodyText"],
        ),
    ]
    SimpleDocTemplate(str(pdf), pagesize=letter).build(story)


def build_safe(diagram: Path, pdf: Path) -> None:
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SAT-SAFE-002 Safe Mode Recovery", styles["Title"]),
        Spacer(1, 0.15 * inch),
        Paragraph(
            "Use this procedure after an attitude fault. The spacecraft sheds the payload, points at the sun, and waits for ground command.",
            styles["BodyText"],
        ),
        Spacer(1, 0.15 * inch),
        Paragraph("Recovery path", styles["Heading2"]),
        RLImage(str(diagram), width=6.5 * inch, height=2.0 * inch),
        Spacer(1, 0.15 * inch),
        Paragraph(
            "The diagram shows Fault Detect, then Safe Mode, then Sun Point. "
            "Sun point is complete when the solar array current is above 1.5 A.",
            styles["BodyText"],
        ),
        Spacer(1, 0.15 * inch),
        _table(
            [
                ["Signal", "Safe-mode value", "Meaning"],
                ["Payload switch", "Open", "Payload is unpowered"],
                ["Array current", "Above 1.5 A", "Sun point is holding"],
                ["Reaction wheel", "Off", "Wheels are safed"],
            ]
        ),
    ]
    SimpleDocTemplate(str(pdf), pagesize=letter).build(story)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    power_png = OUT / "_power_diagram.png"
    safe_png = OUT / "_safe_diagram.png"
    draw_power_diagram(power_png)
    draw_safe_diagram(safe_png)
    build_power(power_png, OUT / "SAT-PWR-001-power-up.pdf")
    build_safe(safe_png, OUT / "SAT-SAFE-002-safe-mode.pdf")
    power_png.unlink()
    safe_png.unlink()
    print("Wrote sample procedures in", OUT)


if __name__ == "__main__":
    main()

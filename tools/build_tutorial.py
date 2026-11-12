"""Build the concept guide, extracting marked code examples from the real sources.

Usage: python tools/build_tutorial.py
Requires the optional requirements/docs.txt dependencies.
"""

import ast
import html
import re
import textwrap
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "FastAPI-Field-Guide.pdf"
PAGE_W, PAGE_H = A4
MARGIN = 47
WIDTH = PAGE_W - MARGIN * 2
INK = colors.HexColor("#142438")
TEAL = colors.HexColor("#007F82")
MUTED = colors.HexColor("#586A7C")
PALE = colors.HexColor("#EDF6F6")

font_dir = Path(reportlab.__file__).parent / "fonts"
for name, filename in (("Body", "Vera.ttf"), ("Bold", "VeraBd.ttf"), ("Italic", "VeraIt.ttf")):
    pdfmetrics.registerFont(TTFont(name, str(font_dir / filename)))
pdfmetrics.registerFontFamily(
    "Body", normal="Body", bold="Bold", italic="Italic", boldItalic="Bold"
)

STYLES = {
    "body": ParagraphStyle(
        "Body",
        fontName="Body",
        fontSize=9.3,
        leading=14.6,
        textColor=INK,
        spaceAfter=9,
        allowWidows=0,
        allowOrphans=0,
    ),
    "h1": ParagraphStyle(
        "Chapter",
        fontName="Bold",
        fontSize=24,
        leading=30,
        textColor=INK,
        spaceBefore=7,
        spaceAfter=20,
        keepWithNext=True,
    ),
    "h2": ParagraphStyle(
        "Section",
        fontName="Bold",
        fontSize=13,
        leading=18,
        textColor=TEAL,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    ),
    "h3": ParagraphStyle(
        "Question",
        fontName="Bold",
        fontSize=10.2,
        leading=15,
        textColor=INK,
        spaceBefore=13,
        spaceAfter=6,
        keepWithNext=True,
    ),
    "label": ParagraphStyle(
        "Label", fontName="Body", fontSize=7.1, leading=10, textColor=colors.HexColor("#C4D9ED")
    ),
    "code": ParagraphStyle(
        "Code",
        fontName="Courier",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#E7F0F9"),
        alignment=TA_LEFT,
    ),
    "cell": ParagraphStyle("Cell", fontName="Body", fontSize=8, leading=12, textColor=INK),
    "head": ParagraphStyle("Head", fontName="Bold", fontSize=8, leading=12, textColor=colors.white),
    "bullet": ParagraphStyle(
        "Bullet",
        fontName="Body",
        fontSize=9.3,
        leading=14.6,
        textColor=INK,
        leftIndent=12,
        firstLineIndent=-9,
        spaceAfter=5,
    ),
}


def inline(value: str) -> str:
    value = html.escape(value)
    value = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#007F82">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    return re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" color="#007F82">\1</a>', value
    )


def paragraph(value: str, style: str = "body") -> Paragraph:
    return Paragraph(inline(value), STYLES[style])


def code_block(source: str, label: str) -> list:
    """Keep snippets legible; long excerpts continue in separately labeled panels."""
    lines = []
    for line in source.rstrip().splitlines():
        lines.extend(
            textwrap.wrap(line, 98, replace_whitespace=False, drop_whitespace=False) or [""]
        )
    blocks = []
    for start in range(0, len(lines), 30):
        chunk = lines[start : start + 30]
        heading = label + ("  |  continued" if start else "")
        table = Table(
            [
                [paragraph(heading, "label")],
                [XPreformatted(html.escape("\n".join(chunk)), STYLES["code"])],
            ],
            colWidths=[WIDTH],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#21374F")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#142438")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 11),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        table.spaceBefore = 5
        table.spaceAfter = 12
        # A snippet's source label must stay on the same page as its code panel.
        blocks.append(KeepTogether([table]))
    return blocks


def extract_code(path: str, symbol: str) -> tuple[str, str]:
    source = (ROOT / path).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == symbol
        ):
            decorators = getattr(node, "decorator_list", [])
            first = min([node.lineno] + [item.lineno for item in decorators])
            excerpt = "\n".join(source.splitlines()[first - 1 : node.end_lineno])
            return textwrap.dedent(
                excerpt
            ), f"REPOSITORY  /  {path}  /  lines {first}-{node.end_lineno}"
    raise ValueError(f"Cannot find {symbol} in {path}")


class Diagram(Flowable):
    """Small vector diagrams remain crisp when readers zoom or print."""

    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.width, self.height = WIDTH, 102

    def draw(self):
        canvas = self.canv
        labels = {
            "request": ["Client", "ASGI server", "Dependencies", "Route + DB", "Response"],
            "auth": ["Login form", "Hash check", "Signed JWT", "Claim check", "Account lookup"],
            "transaction": ["Session", "Read / write", "Flush SQL", "Commit", "Close"],
        }[self.kind]
        box_width = (WIDTH - 16 * 4) / 5
        for index, label in enumerate(labels):
            x = index * (box_width + 16)
            canvas.setFillColor(PALE)
            canvas.setStrokeColor(colors.HexColor("#BBDDDD"))
            canvas.roundRect(x, 40, box_width, 40, 5, fill=1, stroke=1)
            canvas.setFillColor(INK)
            canvas.setFont("Bold", 7.5)
            canvas.drawCentredString(x + box_width / 2, 56, label)
            if index < 4:
                canvas.setStrokeColor(TEAL)
                canvas.line(x + box_width + 3, 60, x + box_width + 12, 60)
                canvas.line(x + box_width + 9, 63, x + box_width + 12, 60)
                canvas.line(x + box_width + 9, 57, x + box_width + 12, 60)
        canvas.setFont("Body", 8)
        canvas.setFillColor(MUTED)
        captions = {
            "request": (
                "Validation and dependency failures can end the request before the route runs."
            ),
            "auth": (
                "Later requests send the bearer JWT; ownership is checked separately for writes."
            ),
            "transaction": (
                "If a write fails: rollback. Session cleanup still runs after the request."
            ),
        }
        canvas.drawString(0, 18, captions[self.kind])


def data_table(rows: list[list[str]]) -> Table:
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        raise ValueError("Inconsistent table columns")
    widths = [WIDTH * 0.30, WIDTH * 0.70] if columns == 2 else [WIDTH / columns] * columns
    table = Table(
        [
            [paragraph(value, "head" if index == 0 else "cell") for value in row]
            for index, row in enumerate(rows)
        ],
        colWidths=widths,
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F1F6F8"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, TEAL),
            ]
        )
    )
    table.spaceBefore, table.spaceAfter = 5, 12
    return table


def cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#46DDD0"))
    canvas.rect(MARGIN, PAGE_H - 131, 48, 5, fill=1, stroke=0)
    canvas.setFont("Bold", 10)
    canvas.drawString(MARGIN, PAGE_H - 108, "CONCEPTS  /  CODE  /  INTERVIEWS")
    canvas.setFillColor(colors.white)
    canvas.setFont("Bold", 47)
    canvas.drawString(MARGIN - 2, PAGE_H - 232, "FastAPI")
    canvas.drawString(MARGIN - 2, PAGE_H - 293, "Field Guide")
    canvas.setFont("Body", 13)
    canvas.setFillColor(colors.HexColor("#C6D7E7"))
    canvas.drawString(MARGIN, PAGE_H - 344, "Build understanding. Revisit the details.")
    canvas.drawString(MARGIN, PAGE_H - 366, "Explain the decisions with confidence.")
    canvas.setStrokeColor(colors.HexColor("#37516C"))
    canvas.line(MARGIN, 310, PAGE_W - MARGIN, 310)
    canvas.setFont("Bold", 11)
    canvas.setFillColor(colors.white)
    canvas.drawString(MARGIN, 279, "A concept-first guide with working project examples")
    canvas.setFont("Body", 10)
    for index, line in enumerate(
        [
            "HTTP and validation  /  Dependencies and SQLAlchemy",
            "Transactions and migrations  /  Passwords and JWT",
            "Testing and deployment  /  Architecture and tradeoffs",
        ]
    ):
        canvas.setFillColor(colors.HexColor("#BED0E1"))
        canvas.drawString(MARGIN, 251 - index * 22, line)
    canvas.setFillColor(colors.HexColor("#46DDD0"))
    canvas.setFont("Bold", 10)
    canvas.drawString(MARGIN, 119, "48 INTERVIEW QUESTIONS WITH MODEL ANSWERS")
    canvas.setFont("Body", 9)
    canvas.setFillColor(colors.HexColor("#BED0E1"))
    canvas.drawString(MARGIN, 94, "Easy  /  Medium  /  Hard  /  Architect")
    canvas.drawString(MARGIN, 49, "REFERENCE EDITION  ·  NOVEMBER 2026")
    canvas.restoreState()


def page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setFont("Bold", 7.5)
    canvas.setFillColor(TEAL)
    canvas.drawString(MARGIN, PAGE_H - 34, "FASTAPI FIELD GUIDE")
    canvas.setFont("Body", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 34, "CONCEPTS + PRACTICE")
    canvas.setStrokeColor(colors.HexColor("#DCE6EC"))
    canvas.line(MARGIN, PAGE_H - 43, PAGE_W - MARGIN, PAGE_H - 43)
    canvas.line(MARGIN, 37, PAGE_W - MARGIN, 37)
    canvas.setFont("Body", 7)
    canvas.drawString(MARGIN, 23, "Products API  /  Learning and revision reference")
    canvas.drawRightString(PAGE_W - MARGIN, 23, f"{doc.page:02d}")
    canvas.restoreState()


class GuideDoc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "Chapter":
            title = flowable.getPlainText()
            key = re.sub(r"\W+", "-", title).lower()
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=0)
            self.notify("TOCEntry", (0, title, self.page, key))


def parse_source(source: str) -> list:
    lines = source.splitlines()
    story, index = [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("# "):
            story.extend([PageBreak(), paragraph(line[2:], "h1")])
        elif line.startswith("### "):
            story.append(paragraph(line[4:], "h3"))
        elif line.startswith("## "):
            story.append(paragraph(line[3:], "h2"))
        elif line == "{{pagebreak}}":
            story.append(PageBreak())
        elif line.startswith("{{code:"):
            path, symbol = line.removeprefix("{{code:").removesuffix("}}").split(":")
            code, label = extract_code(path, symbol)
            story.extend(code_block(code, label))
        elif line.startswith("{{diagram:"):
            story.append(Diagram(line.removeprefix("{{diagram:").removesuffix("}}")))
        elif line.startswith("```"):
            language = line[3:] or "text"
            code, index = [], index + 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            story.extend(code_block("\n".join(code), f"ILLUSTRATION  /  {language}"))
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                values = [value.strip() for value in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", value) for value in values):
                    rows.append(values)
                index += 1
            story.append(data_table(rows))
            continue
        elif line.startswith("> "):
            table = Table([[paragraph(line[2:])]], colWidths=[WIDTH])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), PALE),
                        ("LINEBEFORE", (0, 0), (-1, -1), 3, TEAL),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            table.spaceAfter = 12
            story.append(table)
        elif line.startswith("- "):
            story.append(paragraph("• " + line[2:], "bullet"))
        else:
            story.append(paragraph(line))
        index += 1
    return story


def main() -> None:
    doc = GuideDoc(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=63,
        bottomMargin=51,
        title="FastAPI Field Guide",
        subject="FastAPI concepts with repository examples and 48 interview answers",
        author="",
        pageCompression=1,
    )
    frame = Frame(
        MARGIN,
        51,
        WIDTH,
        PAGE_H - 114,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="Cover", frames=[frame], onPage=cover),
            PageTemplate(id="Body", frames=[frame], onPage=page_chrome),
        ]
    )
    toc = TableOfContents()
    toc.tableStyle = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )
    toc.levelStyles = [
        ParagraphStyle(
            "Contents",
            fontName="Body",
            fontSize=9,
            leading=14,
            textColor=INK,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=0,
        )
    ]
    story = [
        Spacer(1, 5),
        NextPageTemplate("Body"),
        PageBreak(),
        paragraph("Contents", "h2"),
        paragraph("Read sequentially for a first pass, or jump to a concept for revision."),
        toc,
    ]
    story.extend(parse_source((ROOT / "docs" / "tutorial.md").read_text(encoding="utf-8")))
    doc.multiBuild(story)
    print(f"Built {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()

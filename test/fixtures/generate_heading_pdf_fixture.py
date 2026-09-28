#!/usr/bin/env python3
"""
Generate a single-page PDF with a two-level numbered heading outline.

Headings are set in Helvetica-Bold (16 pt for "1 ...", 13 pt for "1.1 ..."),
body text in Helvetica 11 pt, so both the numbering and the style signals of
Docling's heading-hierarchy stage have something to read. Hand-crafted PDF 1.4,
no external library.
"""
import os

FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))

BODY = (
    "Retrieval quality depends on the heading path attached to every chunk, "
    "because the chunker copies it into the text that gets embedded."
)

# (font resource, size, text); headings are numbered like a report outline.
BLOCKS = [
    ("F2", 16, "1 Introduction"),
    ("F1", 11, BODY),
    ("F2", 13, "1.1 Scope of the study"),
    ("F1", 11, BODY),
    ("F2", 13, "1.2 Related work"),
    ("F1", 11, BODY),
    ("F2", 16, "2 Methods"),
    ("F1", 11, BODY),
    ("F2", 13, "2.1 Data collection"),
    ("F1", 11, BODY),
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int = 80) -> list:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def make_heading_pdf() -> bytes:
    commands, y = "", 790
    for font, size, text in BLOCKS:
        y -= 14 if font == "F2" else 4
        for line in _wrap(text):
            commands += f"BT\n/{font} {size} Tf\n50 {y} Td\n({_escape(line)}) Tj\nET\n"
            y -= size + 4
        y -= 6

    stream = commands.encode("latin-1")
    bodies = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 6 0 R"
            b" /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> >>"
        ),
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        6: f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    }

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(bodies):
        offsets[num] = len(out)
        out.extend(f"{num} 0 obj\n".encode() + bodies[num] + b"\nendobj\n")
    xref_offset = len(out)
    out.extend(f"xref\n0 {len(bodies) + 1}\n0000000000 65535 f \n".encode())
    for num in sorted(bodies):
        out.extend(f"{offsets[num]:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(out)


def generate_heading_pdf_fixture() -> str:
    path = os.path.join(FIXTURES_DIR, "sample_headings.pdf")
    with open(path, "wb") as fh:
        fh.write(make_heading_pdf())
    return path


if __name__ == "__main__":
    print(generate_heading_pdf_fixture())

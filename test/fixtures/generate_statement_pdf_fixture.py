#!/usr/bin/env python3
"""
Generate a three-page PDF laid out like an IPCC Summary for Policymakers.

Pages 1 and 2 have a section ("A. ...", Helvetica-Bold 16), a side heading (Helvetica-
Bold 13) and four numbered statements ("A.1 ..." to "A.4 ...") of
several lines set in Helvetica-Bold at body size (11 pt), each followed by
sub-statements ("A.1.1 ...") in the body face, Helvetica 11 pt. Page 3 holds
the false-positive set: a bold callout without numbering, a code listing in
Courier, a quote in Helvetica-Oblique and numbered footnotes in a smaller
oblique face. Hand-crafted PDF 1.4, no external library, same technique as
generate_heading_pdf_fixture.py.
"""

import os

FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))

FONTS = {
    "F1": "Helvetica",
    "F2": "Helvetica-Bold",
    "F3": "Courier",
    "F4": "Helvetica-Oblique",
}

# Sub-statements and body paragraphs, in the body face. There is enough of it
# for the statement face to stay a minority of the document, as in the
# reports this layout comes from.
SUB = (
    "Global surface temperature was 1.09 degrees higher in 2011-2020 than in "
    "1850-1900, with larger increases over land than over the ocean, and the "
    "rate of increase in the last fifty years is the fastest in two millennia. "
    "The likely range of total human-caused global surface temperature increase "
    "over the same period is close to the observed warming, and observed "
    "increases in well-mixed greenhouse gas concentrations are unequivocally "
    "caused by human activities, from energy use to land-use change."
)

STATEMENTS = {
    "A.1": (
        "A.1 Human activities, principally through emissions of greenhouse gases, "
        "have unequivocally caused global warming, with global surface temperature "
        "reaching 1.1 degrees above 1850-1900 in 2011-2020. Global greenhouse gas "
        "emissions have continued to increase, with unequal contributions."
    ),
    "A.2": (
        "A.2 Widespread and rapid changes in the atmosphere, ocean, cryosphere and "
        "biosphere have occurred. Human-caused climate change is already affecting "
        "many weather and climate extremes in every region across the globe, with "
        "widespread adverse impacts and related losses and damages to nature."
    ),
    "A.3": (
        "A.3 Adaptation planning and implementation has progressed across all "
        "sectors and regions, with documented benefits and varying effectiveness. "
        "Despite progress, adaptation gaps exist, and will continue to grow at "
        "current rates of implementation, and limits have been reached in places."
    ),
    "A.4": (
        "A.4 Policies and laws addressing mitigation have consistently expanded "
        "since the previous assessment. Global greenhouse gas emissions in 2030 "
        "implied by nationally determined contributions announced by October 2021 "
        "make it likely that warming will exceed 1.5 degrees during this century."
    ),
}

# (font resource, size, text) per block; None starts a new page.
BLOCKS = [
    ("F2", 16, "A. Current Status and Trends"),
    ("F2", 13, "Observed Warming and its Causes"),
    ("F2", 11, STATEMENTS["A.1"]),
    ("F1", 11, "A.1.1 " + SUB),
    ("F1", 11, "A.1.2 " + SUB),
    ("F1", 11, "A.1.3 " + SUB),
    ("F2", 13, "Observed Changes and Impacts"),
    ("F2", 11, STATEMENTS["A.2"]),
    ("F1", 11, "A.2.1 " + SUB),
    ("F1", 11, "A.2.2 " + SUB),
    None,
    ("F2", 13, "Current Progress in Adaptation"),
    ("F2", 11, STATEMENTS["A.3"]),
    ("F1", 11, "A.3.1 " + SUB),
    ("F1", 11, "A.3.2 " + SUB),
    ("F1", 11, "A.3.3 " + SUB),
    ("F2", 13, "Current Progress in Mitigation"),
    ("F2", 11, STATEMENTS["A.4"]),
    ("F1", 11, "A.4.1 " + SUB),
    ("F1", 11, "A.4.2 " + SUB),
    None,
    ("F2", 16, "B. Notes on Method"),
    (
        "F1",
        11,
        "This page carries the material a statement pass must leave alone. " + SUB,
    ),
    (
        "F2",
        11,
        "Key message: the heading path attached to every chunk decides what the "
        "retriever sees, because the chunker copies it into the embedded text. "
        "A callout in bold is emphasis, not a section of the report.",
    ),
    (
        "F1",
        11,
        "The listing below is set in a monospaced face at a smaller size. " + SUB,
    ),
    ("F3", 10, "def chunk(document):"),
    ("F3", 10, "    for item, level in document.iterate_items():"),
    ("F3", 10, "        yield item.text, level"),
    (
        "F4",
        11,
        "We are the first generation to feel the effect of climate change and the "
        "last generation who can do something about it, as the saying goes.",
    ),
    ("F1", 11, "Numbered footnotes follow, in a smaller oblique face. " + SUB),
    (
        "F4",
        9,
        "1 The three Working Group contributions to the Sixth Assessment Report are "
        "the physical science basis, impacts and adaptation, and mitigation.",
    ),
    (
        "F4",
        9,
        "2 The three Special Reports cover global warming of 1.5 degrees, climate "
        "change and land, and the ocean and cryosphere in a changing climate.",
    ),
    (
        "F4",
        9,
        "3 In this report the near term is defined as the period until 2040, and "
        "the long term as the period from 2081 to 2100, following the assessment.",
    ),
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int) -> list:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def _page_commands(blocks: list) -> bytes:
    commands, y = "", 790
    for font, size, text in blocks:
        y -= 14 if size > 11 else 4
        # Bold and Courier are wider than Helvetica: wrap them earlier.
        width = 72 if font in ("F2", "F3") else 80
        for line in _wrap(text, width):
            commands += f"BT\n/{font} {size} Tf\n50 {y} Td\n({_escape(line)}) Tj\nET\n"
            y -= size + 3
        y -= 12
    return commands.encode("latin-1")


def make_statement_pdf() -> bytes:
    pages: list = [[]]
    for block in BLOCKS:
        if block is None:
            pages.append([])
        else:
            pages[-1].append(block)

    bodies: dict = {}
    font_objs = {}
    next_obj = 3
    for key, base in FONTS.items():
        font_objs[key] = next_obj
        bodies[next_obj] = (
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} >>".encode()
        )
        next_obj += 1
    resources = " ".join(f"/{key} {num} 0 R" for key, num in font_objs.items())

    page_objs = []
    for blocks in pages:
        stream = _page_commands(blocks)
        content_obj = next_obj
        page_obj = next_obj + 1
        next_obj += 2
        bodies[content_obj] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
        bodies[page_obj] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents {content_obj} 0 R"
            f" /Resources << /Font << {resources} >> >> >>"
        ).encode()
        page_objs.append(page_obj)

    kids = " ".join(f"{num} 0 R" for num in page_objs)
    bodies[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    bodies[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_objs)} >>".encode()

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


def generate_statement_pdf_fixture() -> str:
    path = os.path.join(FIXTURES_DIR, "sample_statements.pdf")
    with open(path, "wb") as fh:
        fh.write(make_statement_pdf())
    return path


if __name__ == "__main__":
    print(generate_statement_pdf_fixture())

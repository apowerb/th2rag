#!/usr/bin/env python3
"""
Generate a minimal but real PDF fixture for Docling 2.73 non-regression tests.

No external PDF library required: the PDF is hand-crafted in bytes using the
PDF 1.4 spec (text-only, single page, Helvetica Type1 font, multiple BT/ET blocks).

Design constraint: each paragraph is its own BT/ET block so that Docling 2.73
extracts them as separate text items. The total word count exceeds the TOKEN_THRESHOLD
(50) used by enable_ocr() so that the two-pass OCR is NOT triggered on this fixture.

The text is extractible by any conformant PDF reader.
"""
import os

FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))


def make_multibt_pdf(paragraphs: list) -> bytes:
    """
    Build a valid single-page PDF 1.4 with one BT/ET block per paragraph.

    Multiple BT/ET blocks ensure Docling 2.73 extracts each paragraph as a
    separate text item, giving a word count well above TOKEN_THRESHOLD=50.
    """
    all_commands = ''
    for i, para in enumerate(paragraphs):
        y = 780 - i * 35
        # Split long lines at word 8 to avoid overflowing page width
        words = para.split()
        line1 = ' '.join(words[:8])
        line2 = ' '.join(words[8:]) if len(words) > 8 else ''
        safe1 = line1.replace('\\', '\\\\').replace(')', '\\)').replace('(', '\\(')
        safe2 = line2.replace('\\', '\\\\').replace(')', '\\)').replace('(', '\\(')
        all_commands += f'BT\n/F1 12 Tf\n50 {y} Td\n({safe1}) Tj\nET\n'
        if safe2:
            y2 = y - 15
            all_commands += f'BT\n/F1 11 Tf\n50 {y2} Td\n({safe2}) Tj\nET\n'

    stream_bytes = all_commands.encode('latin-1')
    stream_length = len(stream_bytes)

    obj_bodies = {
        1: b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        2: b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        3: (
            b'3 0 obj\n<< /Type /Page /Parent 2 0 R\n'
            b'   /MediaBox [0 0 612 842]\n'
            b'   /Contents 5 0 R\n'
            b'   /Resources << /Font << /F1 4 0 R >> >> >>\nendobj\n'
        ),
        4: b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
        5: (
            f'5 0 obj\n<< /Length {stream_length} >>\nstream\n'.encode()
            + stream_bytes
            + b'\nendstream\nendobj\n'
        ),
    }

    result = bytearray(b'%PDF-1.4\n')
    offsets: dict = {}
    for num in sorted(obj_bodies):
        offsets[num] = len(result)
        result.extend(obj_bodies[num])

    xref_offset = len(result)
    xref = 'xref\n0 6\n0000000000 65535 f \n'
    for num in range(1, 6):
        xref += f'{offsets[num]:010d} 00000 n \n'
    result.extend(xref.encode())

    trailer = (
        f'trailer\n<< /Size 6 /Root 1 0 R >>\n'
        f'startxref\n{xref_offset}\n%%EOF\n'
    )
    result.extend(trailer.encode())
    return bytes(result)


def generate_pdf_fixture() -> str:
    """
    Generate sample_text.pdf with > TOKEN_THRESHOLD words so enable_ocr() returns False.
    TOKEN_THRESHOLD = 50 (see pdf_converter.py).
    """
    paragraphs = [
        'th2rag RAG Non-Regression Test Fixture pour Docling 2.73',
        'Section 1: Verification de la conversion PDF sans regression',
        'Ce document teste extraction texte multi-paragraphes via DocumentConverter',
        'Section 2: API Surface PdfPipelineOptions ThreadedPdfPipelineOptions intact',
        'get_pipeline_options retourne des options valides sans DeprecationError',
        'Section 3: Chunking produit un token count superieur a zero chunks confirme',
        'convert_with_docling ne leve pas exception sur ce PDF valide format 1.4',
        'Section 4: Lorem ipsum dolor sit amet consectetur adipiscing elit sed do',
        'eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim',
        'Section 5: Verification pipeline Docling 2.73 bump from 2.20 no regression',
    ]
    pdf_bytes = make_multibt_pdf(paragraphs)
    path = os.path.join(FIXTURES_DIR, 'sample_text.pdf')
    with open(path, 'wb') as f:
        f.write(pdf_bytes)
    print(f'Generated: {path} ({len(pdf_bytes)} bytes)')
    return path


if __name__ == '__main__':
    generate_pdf_fixture()

import io

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF.
    Tries embedded text first (fast). Falls back to OCR for scanned pages.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        # WALKTHROUGH: the cheap path first, per page. A "digital" PDF (exported
        # from Word, a county system, etc.) carries a real text layer — get_text()
        # returns it instantly and perfectly, no OCR needed. Only when a page has
        # NO text layer (a scanned image of paper) do we fall to the expensive
        # path: rasterize the page at 300 DPI and run pytesseract OCR on the
        # pixels. The decision is per-page, not per-document, because real-world
        # PDFs mix both — a digital form with a scanned signature page. 300 DPI is
        # the sweet spot: high enough for clean OCR, not so high it's slow.
        text = page.get_text().strip()
        if text:
            pages.append(text)
        else:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img)
            pages.append(ocr_text.strip())
    doc.close()
    return "\n\n--- PAGE BREAK ---\n\n".join(pages)


def extract_text_from_image(file_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(img)


def extract_text(file_bytes: bytes, file_type: str) -> str:
    """Main entry point — extract text from any supported file type."""
    if file_type == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif file_type == "image":
        return extract_text_from_image(file_bytes)
    elif file_type in ("text", "csv", "xml"):
        # WALKTHROUGH: already-text formats skip OCR entirely — just decode the
        # bytes. errors="replace" means a stray bad byte becomes a placeholder
        # char instead of throwing, so one malformed character can't fail the
        # whole document. (Structured XML may later take an even faster path —
        # see xml_parser — but it still needs decodable text here as a fallback.)
        return file_bytes.decode("utf-8", errors="replace")
    return ""

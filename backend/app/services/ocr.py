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
        return file_bytes.decode("utf-8", errors="replace")
    return ""

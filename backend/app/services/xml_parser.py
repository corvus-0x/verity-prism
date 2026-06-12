"""
Direct XML parser for structured document types (IRS 990, etc.).
Bypasses OCR and Claude extraction when the source is already structured XML.
Field paths in the schema description are used to locate values in the XML tree.
"""

import logging
import re
import xml.etree.ElementTree as ET

from app.models.document_schema import DocumentSchema

logger = logging.getLogger(__name__)

# IRS 990 XML namespace
IRS_NS = "{http://www.irs.gov/efile}"


def _strip_ns(tag: str) -> str:
    return re.sub(r"\{[^}]+\}", "", tag)


def _find_by_path(root: ET.Element, dotted_path: str) -> str | None:
    """
    Walk a dotted element path like 'ReturnHeader.TaxYr' through the XML tree.
    Tries both with and without the IRS namespace prefix.
    Returns the text of the first matching element, or None.
    """
    # WALKTHROUGH: real-world XML is messy about namespaces — the same IRS 990
    # field might appear as {irs.gov}TaxYr or bare TaxYr depending on the filer's
    # software. Rather than demand one form, each step tries four locators in
    # order of specificity: (1) direct child WITH the IRS namespace, (2) direct
    # child WITHOUT it, (3) anywhere in the subtree with namespace, (4) anywhere
    # without. First hit wins. This tolerance is why the parser survives format
    # drift across thousands of differently-generated filings.
    parts = dotted_path.split(".")
    current = [root]
    for part in parts:
        next_nodes = []
        for node in current:
            # Try with IRS namespace
            found = node.find(f"{IRS_NS}{part}")
            if found is not None:
                next_nodes.append(found)
                continue
            # Try without namespace
            found = node.find(part)
            if found is not None:
                next_nodes.append(found)
                continue
            # Try searching anywhere in subtree
            found = node.find(f".//{IRS_NS}{part}")
            if found is not None:
                next_nodes.append(found)
                continue
            found = node.find(f".//{part}")
            if found is not None:
                next_nodes.append(found)
        current = next_nodes
        if not current:
            return None
    return current[0].text.strip() if current and current[0].text else None


def _extract_path_from_description(description: str) -> str | None:
    """
    Pull the XML element path from a field description.
    Descriptions contain paths like: 'ReturnHeader/TaxYr — description text'
    or 'IRS990/GrossReceiptsAmt — description'.
    Returns the dotted path (slashes converted to dots) or None.
    """
    # Match the first word-path segment before ' —' or end of line
    match = re.match(r"^([A-Za-z0-9_/]+(?:\.[A-Za-z0-9_/]+)*)", description.strip())
    if not match:
        return None
    raw = match.group(1)
    # Convert slashes to dots for our path walker
    return raw.replace("/", ".")


def parse_xml_document(
    file_bytes: bytes,
    schema: DocumentSchema,
) -> list[dict]:
    """
    Parse a structured XML document directly using field paths from the schema.
    Returns a list of dicts in the same format as extract_fields() so the
    pipeline can call save_extractions() uniformly for both paths.

    Confidence is always 1.0 — direct parse has no interpretation uncertainty.
    """
    # WALKTHROUGH: this is the "no AI needed" extraction path. When a document is
    # already structured (an IRS 990 e-file is XML), reading a field is a tree
    # lookup, not an act of interpretation — so confidence is a flat 1.0 and no
    # Claude call happens. Crucially, it returns the SAME list[dict] shape that
    # extract_fields() (the Claude path) returns, so document_pipeline can call
    # save_extractions() identically for both. The cleverness is invisible to the
    # caller: deterministic vs AI extraction is a schema decision, not a code fork
    # downstream. (See the parse_strategy fork in document_pipeline.)
    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}")
        return []

    extractions = []
    for field in schema.schema_fields:
        field_name = field.get("name", "")
        field_type = field.get("type", "text")
        description = field.get("description", "")

        path = _extract_path_from_description(description)
        if not path:
            continue

        value = _find_by_path(root, path)
        if value is None:
            continue

        extractions.append(
            {
                "field_name": field_name,
                "field_value": value,
                "field_type": field_type,
                "confidence": 1.0,
                "ocr_confidence": 1.0,
            }
        )

    logger.info(
        f"XML direct parse: {len(extractions)} fields extracted using schema {schema.document_type}"
    )
    return extractions


def is_valid_xml_bytes(file_bytes: bytes) -> bool:
    """Return True if file_bytes are parseable XML.
    Used by the pipeline to guard the xml_direct parse path. Unlike
    is_parseable_xml(), this does not check document type — the schema's
    parse_strategy field owns that decision.
    """
    if not file_bytes:
        return False
    try:
        ET.fromstring(file_bytes)
        return True
    except ET.ParseError:
        return False

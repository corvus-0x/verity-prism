"""
Direct XML parser for structured document types (IRS 990, etc.).
Bypasses OCR and Claude extraction when the source is already structured XML.
Field paths in the schema description are used to locate values in the XML tree.
"""
import xml.etree.ElementTree as ET
import re
import logging
from sqlalchemy.orm import Session
from app.models.document_schema import DocumentSchema
from app.models.document_extraction import DocumentExtraction

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
    document_id: str,
    workspace_id: str,
    db: Session,
) -> list[DocumentExtraction]:
    """
    Parse a structured XML document directly using field paths from the schema.
    Returns a list of DocumentExtraction rows saved to the database.
    Used for IRS 990 XML and any other structured XML document type.
    """
    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as e:
        logger.error(f"XML parse error for doc {document_id}: {e}")
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

        row = DocumentExtraction(
            document_id=document_id,
            workspace_id=workspace_id,
            field_name=field_name,
            field_value=value,
            field_type=field_type,
            confidence=1.0,  # Direct parse = certain
            schema_id=schema.id,
        )
        db.add(row)
        extractions.append(row)

    if extractions:
        db.commit()
        logger.info(
            f"XML direct parse: {len(extractions)} fields extracted "
            f"for doc {document_id} using schema {schema.document_type}"
        )

    return extractions


def is_parseable_xml(file_bytes: bytes, doc_type: str) -> bool:
    """Return True if this document should use the direct XML parse path."""
    xml_schema_types = {"990", "990-T"}
    if doc_type not in xml_schema_types:
        return False
    try:
        ET.fromstring(file_bytes)
        return True
    except ET.ParseError:
        return False

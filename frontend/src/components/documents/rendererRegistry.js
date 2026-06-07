import DigitalDocumentRenderer from "./DigitalDocumentRenderer";

// Engine ships only the generic renderer.
// Caps register faithful per-type templates in Phase 3 via registerRenderer(docType, Component).
const _faithful = {};

export function registerRenderer(docType, component) {
  _faithful[docType] = component;
}

export function getRenderer(docType, renderMode) {
  if (renderMode === "faithful" && _faithful[docType]) return _faithful[docType];
  return DigitalDocumentRenderer;
}

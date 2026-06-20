import { findFieldTextMatches } from '../../hooks/useFieldHighlight'

export function pdfRegionToScreenMatch(region, pageViewport) {
  if (!region || !pageViewport) return null

  return {
    x: region.x,
    y: pageViewport.height - region.y - region.height,
    width: region.width,
    height: region.height,
  }
}

export function buildPageSearchOrder(currentPage, totalPages) {
  const safeCurrent = Math.min(Math.max(currentPage || 1, 1), totalPages || 1)
  const order = [safeCurrent]

  for (let page = 1; page <= totalPages; page += 1) {
    if (page !== safeCurrent) order.push(page)
  }

  return order
}

export async function getCachedPageText(pdfProxy, pageNumber, cache) {
  const cached = cache.get(pageNumber)
  if (cached) return cached

  const page = await pdfProxy.getPage(pageNumber)
  const viewport = page.getViewport({ scale: 1.0 })
  const content = await page.getTextContent()
  const payload = { viewport, items: content.items }

  cache.set(pageNumber, payload)
  return payload
}

export async function findFirstMatchingPage({
  pdfProxy,
  fieldValue,
  currentPage,
  cache,
}) {
  if (!pdfProxy || !fieldValue) return null

  const order = buildPageSearchOrder(currentPage, pdfProxy.numPages || 1)

  for (const pageNumber of order) {
    const { viewport, items } = await getCachedPageText(pdfProxy, pageNumber, cache)
    const matches = findFieldTextMatches(fieldValue, items, viewport)

    if (matches.length > 0) {
      return { pageNumber, matches }
    }
  }

  return null
}

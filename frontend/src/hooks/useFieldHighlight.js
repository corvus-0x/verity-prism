// frontend/src/hooks/useFieldHighlight.js
import { useMemo, useState, useCallback, useEffect } from 'react'

/**
 * Searches PDF text layer items for a field value.
 * Returns match coordinates (in PDF coordinate space) and navigation helpers.
 *
 * fieldValue: string to search for (or null/empty = no matches)
 * textItems: array of text items from pdfjs page.getTextContent().items
 *   Each item: { str, transform: [a,b,c,d,x,y], width, height }
 *   transform[4] = x position, transform[5] = y position (PDF coords, origin bottom-left)
 * pageViewport: pdfjs viewport object with .width and .height (for y-axis conversion)
 *
 * Returns: { matches, activeIndex, activeMatch, next, prev }
 *   matches: array of { x, y, width, height } in screen pixels (y-flipped to top-left origin)
 *   activeMatch: the currently active match (or null)
 *   next/prev: functions to cycle through matches
 */
export default function useFieldHighlight(fieldValue, textItems, pageViewport) {
  const [activeIndex, setActiveIndex] = useState(0)

  const matches = useMemo(() => {
    if (!fieldValue || !textItems || textItems.length === 0 || !pageViewport) return []

    const normalise = (s) => s.replace(/[\s$,]/g, '').toLowerCase()
    const target = normalise(String(fieldValue))
    if (!target) return []

    const found = []
    // Sliding window: concatenate nearby text items to find multi-word values
    for (let i = 0; i < textItems.length; i++) {
      let window = ''
      for (let j = i; j < Math.min(i + 8, textItems.length); j++) {
        window += textItems[j].str
        if (normalise(window).includes(target)) {
          const item = textItems[i]
          const x = item.transform[4]
          const y = item.transform[5]
          // Convert from PDF bottom-left to top-left (screen) coordinates
          const canvasY = pageViewport.height - y - (item.height || 12)
          found.push({
            x,
            y: canvasY,
            width: item.width + (j - i) * 60,  // approximate multi-item width
            height: (item.height || 12) + 4,
          })
          break
        }
      }
    }

    // Deduplicate: remove matches within 20px of each other
    return found.filter((m, i) =>
      i === 0 || Math.abs(m.y - found[i - 1].y) > 20 || Math.abs(m.x - found[i - 1].x) > 20
    )
  }, [fieldValue, textItems, pageViewport])

  // Reset to first match whenever the search value changes
  useEffect(() => { setActiveIndex(0) }, [fieldValue])

  const next = useCallback(() => {
    setActiveIndex((i) => (i + 1) % Math.max(matches.length, 1))
  }, [matches.length])

  const prev = useCallback(() => {
    setActiveIndex((i) => (i - 1 + Math.max(matches.length, 1)) % Math.max(matches.length, 1))
  }, [matches.length])

  const safeIndex = Math.min(activeIndex, Math.max(matches.length - 1, 0))

  return {
    matches,
    activeIndex: safeIndex,
    activeMatch: matches[safeIndex] || null,
    next,
    prev,
  }
}

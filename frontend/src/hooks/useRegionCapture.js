import { useCallback } from 'react'

/**
 * Captures a rectangular region from a react-pdf canvas as a base64 PNG.
 * Also supports drag-to-draw region selection overlaid on the PDF.
 *
 * pageContainerRef: React ref pointing to the DOM element wrapping the react-pdf <Page>.
 *   The hook finds the canvas element via querySelector('canvas') on this ref.
 *
 * Returns: { capture(region, pdfHeight, scale), startDraw(pdfHeight, scale, onComplete) }
 *
 * capture(region, pdfHeight, scale):
 *   region: { x, y, width, height } in PDF coordinate space (origin bottom-left)
 *   pdfHeight: page height in PDF units (from viewport.height)
 *   scale: current render scale (typically 1.0)
 *   Returns base64 PNG string, or null if canvas not available
 *
 * startDraw(pdfHeight, scale, onComplete):
 *   Enters drag-to-draw mode on the PDF canvas.
 *   onComplete(region, image_b64): called when operator releases mouse.
 *     region: { x, y, width, height } in PDF coordinate space
 *     image_b64: base64 PNG of the selected area (null if too small)
 */
export function useRegionCapture(pageContainerRef) {
  const capture = useCallback((region, pdfHeight, scale) => {
    const canvas = pageContainerRef.current?.querySelector('canvas')
    if (!canvas) return null

    const sw = Math.round(region.width * scale)
    const sh = Math.round(region.height * scale)
    if (sw <= 0 || sh <= 0) return null

    const offscreen = document.createElement('canvas')
    offscreen.width = sw
    offscreen.height = sh

    const ctx = offscreen.getContext('2d')
    // PDF y-origin is bottom-left; canvas y-origin is top-left — flip y
    const srcX = Math.round(region.x * scale)
    const srcY = Math.round((pdfHeight - region.y - region.height) * scale)

    ctx.drawImage(canvas, srcX, srcY, sw, sh, 0, 0, sw, sh)
    return offscreen.toDataURL('image/png')
  }, [pageContainerRef])

  const startDraw = useCallback((pdfHeight, scale, onComplete) => {
    const container = pageContainerRef.current
    const canvas = container?.querySelector('canvas')
    if (!canvas || !container) return

    const rect = canvas.getBoundingClientRect()
    let startX = 0
    let startY = 0
    let isDragging = false

    // Overlay div to capture mouse events without interfering with PDF rendering
    const overlay = document.createElement('div')
    overlay.style.cssText = [
      'position:absolute', 'top:0', 'left:0', 'right:0', 'bottom:0',
      'cursor:crosshair', 'z-index:50',
    ].join(';')

    // Visual selection box
    const selBox = document.createElement('div')
    selBox.style.cssText = [
      'position:absolute',
      'border:2px solid #3b82f6',
      'background:rgba(59,130,246,0.1)',
      'pointer-events:none',
      'display:none',
    ].join(';')
    overlay.appendChild(selBox)

    // Ensure container is positioned so absolute children are relative to it
    const prevPosition = container.style.position
    container.style.position = 'relative'
    container.appendChild(overlay)

    const cleanup = () => {
      overlay.removeEventListener('mousedown', onMouseDown)
      overlay.removeEventListener('mousemove', onMouseMove)
      overlay.removeEventListener('mouseup', onMouseUp)
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay)
      container.style.position = prevPosition
    }

    const onMouseDown = (e) => {
      isDragging = true
      startX = e.clientX - rect.left
      startY = e.clientY - rect.top
      selBox.style.display = 'block'
      selBox.style.left = startX + 'px'
      selBox.style.top = startY + 'px'
      selBox.style.width = '0'
      selBox.style.height = '0'
    }

    const onMouseMove = (e) => {
      if (!isDragging) return
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const l = Math.min(startX, x)
      const t = Math.min(startY, y)
      selBox.style.left = l + 'px'
      selBox.style.top = t + 'px'
      selBox.style.width = Math.abs(x - startX) + 'px'
      selBox.style.height = Math.abs(y - startY) + 'px'
    }

    const onMouseUp = (e) => {
      if (!isDragging) return
      isDragging = false
      cleanup()

      const endX = e.clientX - rect.left
      const endY = e.clientY - rect.top
      const w = Math.abs(endX - startX)
      const h = Math.abs(endY - startY)

      if (w < 5 || h < 5) {
        onComplete(null, null)
        return
      }

      const l = Math.min(startX, endX)
      const t = Math.min(startY, endY)

      // Convert screen pixels back to PDF coordinate space
      const pdfX = l / scale
      const pdfY = pdfHeight - (t / scale) - (h / scale)
      const region = { x: pdfX, y: pdfY, width: w / scale, height: h / scale }
      const image_b64 = capture(region, pdfHeight, scale)
      onComplete(region, image_b64)
    }

    overlay.addEventListener('mousedown', onMouseDown)
    overlay.addEventListener('mousemove', onMouseMove)
    overlay.addEventListener('mouseup', onMouseUp)
  }, [pageContainerRef, capture])

  return { capture, startDraw }
}

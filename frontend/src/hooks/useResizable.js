import { useState, useRef, useCallback } from 'react'

// direction: 'right' = drag right to expand (left-edge handle)
//            'left'  = drag right to shrink (right-edge handle, e.g. fields pane)
export function useResizable(initialWidth, { min = 120, max = 600, direction = 'right' } = {}) {
  const [width, setWidth] = useState(initialWidth)
  const widthRef = useRef(width)
  widthRef.current = width
  const dragRef = useRef(null)

  const onMouseDown = useCallback((e) => {
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startWidth: widthRef.current }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMouseMove = (e) => {
      if (!dragRef.current) return
      const delta = e.clientX - dragRef.current.startX
      const effective = direction === 'left' ? -delta : delta
      setWidth(Math.max(min, Math.min(max, dragRef.current.startWidth + effective)))
    }

    const onMouseUp = () => {
      dragRef.current = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [min, max, direction])

  return [width, onMouseDown]
}

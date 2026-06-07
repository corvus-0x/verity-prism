import { useState, useRef } from 'react'

export default function ResizeHandle({ onMouseDown }) {
  const [active, setActive] = useState(false)
  const draggingRef = useRef(false)

  const handleMouseDown = (e) => {
    setActive(true)
    draggingRef.current = true
    const onUp = () => {
      draggingRef.current = false
      setActive(false)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mouseup', onUp)
    onMouseDown(e)
  }

  return (
    <div
      onMouseDown={handleMouseDown}
      onMouseEnter={() => setActive(true)}
      onMouseLeave={() => { if (!draggingRef.current) setActive(false) }}
      style={{ width: '6px', flexShrink: 0, cursor: 'col-resize', position: 'relative', zIndex: 10 }}
    >
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: '2px', width: '2px',
        background: active ? '#DC2626' : '#1A2A3F',
        transition: 'background 120ms',
      }} />
    </div>
  )
}

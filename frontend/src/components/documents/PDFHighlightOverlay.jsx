/**
 * Renders a blue highlight box over the active field's location on the PDF.
 * Positioned absolutely over the react-pdf <Page> container via the parent
 * wrapping the Page in a relative-positioned div.
 *
 * Props:
 *   activeMatch: { x, y, width, height } in screen pixels (already scaled) — or null
 *   activeFieldName: string label shown above the highlight box
 *   matchCount: total number of matches (for "1 of N" navigation display)
 *   matchIndex: current match index (0-based)
 *   onNext: () => void — advance to next match
 *   onPrev: () => void — go to previous match
 */
export default function PDFHighlightOverlay({
  activeMatch, activeFieldName, matchCount, matchIndex, onNext, onPrev,
}) {
  if (!activeMatch) return null

  return (
    <div
      style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: 0,
        pointerEvents: 'none',
        zIndex: 10,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: activeMatch.x,
          top: activeMatch.y,
          width: activeMatch.width,
          height: activeMatch.height,
          border: '2px solid #3b82f6',
          background: 'rgba(59,130,246,0.15)',
          borderRadius: 3,
        }}
      >
        {/* Label above the highlight box */}
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: 3,
            background: '#3b82f6',
            color: 'white',
            fontSize: 9,
            padding: '2px 6px',
            borderRadius: 3,
            whiteSpace: 'nowrap',
            pointerEvents: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span>{activeFieldName}</span>
          {matchCount > 1 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <button
                onClick={onPrev}
                style={{
                  background: 'rgba(255,255,255,0.2)', border: 'none',
                  color: 'white', cursor: 'pointer', borderRadius: 2,
                  padding: '0 4px', fontSize: 9, lineHeight: '14px',
                }}
              >
                ◀
              </button>
              <span>{matchIndex + 1}/{matchCount}</span>
              <button
                onClick={onNext}
                style={{
                  background: 'rgba(255,255,255,0.2)', border: 'none',
                  color: 'white', cursor: 'pointer', borderRadius: 2,
                  padding: '0 4px', fontSize: 9, lineHeight: '14px',
                }}
              >
                ▶
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

import { useCallback, useState } from 'react'

export default function DropZone({ onFiles, uploading }) {
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onFiles(files)
  }, [onFiles])

  const handleChange = (e) => {
    const files = Array.from(e.target.files)
    if (files.length) onFiles(files)
    e.target.value = ''
  }

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`block border-2 border-dashed rounded-xl p-6 text-center cursor-pointer
                  transition-colors ${dragging
                    ? 'border-blue-400 bg-blue-950'
                    : 'border-slate-600 hover:border-slate-400'
                  }`}
    >
      <input type="file" multiple className="hidden" onChange={handleChange} accept=".pdf,.png,.jpg,.jpeg,.csv,.txt,.xml" />
      <p className="text-slate-400 text-sm">
        {uploading ? 'Uploading...' : 'Drop files here, or click to browse'}
      </p>
      <p className="text-slate-600 text-xs mt-1">Multiple files supported · PDF, images, XML</p>
    </label>
  )
}

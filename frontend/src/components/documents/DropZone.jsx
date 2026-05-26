import { useCallback, useState } from 'react'

export default function DropZone({ onFile, uploading }) {
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onFile(file)
  }, [onFile])

  const handleChange = (e) => {
    const file = e.target.files[0]
    if (file) onFile(file)
  }

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`block border-2 border-dashed rounded-xl p-10 text-center cursor-pointer
                  transition-colors ${dragging
                    ? 'border-blue-400 bg-blue-950'
                    : 'border-slate-600 hover:border-slate-400'
                  }`}
    >
      <input type="file" className="hidden" onChange={handleChange} accept=".pdf,.png,.jpg,.jpeg,.csv,.txt,.xml" />
      <p className="text-slate-400 text-sm">
        {uploading ? 'Uploading and extracting...' : 'Drag and drop a file here, or click to browse'}
      </p>
      <p className="text-slate-600 text-xs mt-2">PDF, images, spreadsheets, XML</p>
    </label>
  )
}

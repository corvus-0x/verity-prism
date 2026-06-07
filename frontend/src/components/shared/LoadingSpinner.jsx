export default function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div
        className="w-7 h-7 rounded-full animate-spin-ring"
        style={{
          border: '2px solid #1A2A3F',
          borderTopColor: '#DC2626',
        }}
      />
    </div>
  )
}

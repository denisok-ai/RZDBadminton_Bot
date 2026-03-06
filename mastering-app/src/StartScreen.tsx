import { useCallback } from 'react'

type Props = {
  onStart: () => void
  onDrop: (file: File) => void
}

export function StartScreen({ onStart, onDrop }: Props) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const file = e.dataTransfer.files[0]
      if (file && file.type.startsWith('audio/')) {
        onDrop(file)
      }
    },
    [onDrop]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  return (
    <div
      className="start-screen"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <button
        type="button"
        onClick={onStart}
        style={{
          padding: '24px 48px',
          fontSize: 24,
          fontWeight: 600,
          cursor: 'pointer',
          backgroundColor: '#3a7bd5',
          color: '#fff',
          border: 'none',
          borderRadius: 12,
        }}
      >
        Начать
      </button>
      <p style={{ marginTop: 16, opacity: 0.8 }}>
        или перетащите аудиофайл сюда
      </p>
    </div>
  )
}

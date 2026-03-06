import { useState, useCallback, useEffect } from 'react'
import { StartScreen } from './StartScreen'
import { MainScreen } from './MainScreen'
import type { OzonePresetId } from './ozonePresets'

export type TrackFile = {
  file: File
  url: string
}

export default function App() {
  const [track, setTrack] = useState<TrackFile | null>(null)
  const [view, setView] = useState<'start' | 'main'>('start')
  const [ozonePresetId, setOzonePresetId] = useState<OzonePresetId>(() => {
    if (typeof window === 'undefined') return 'house'
    const saved = window.localStorage.getItem('ozonePresetId') as OzonePresetId | null
    return saved ?? 'house'
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('ozonePresetId', ozonePresetId)
  }, [ozonePresetId])

  const goToMain = useCallback(() => {
    setView('main')
  }, [])

  const loadTrack = useCallback((file: File) => {
    const url = URL.createObjectURL(file)
    setTrack({ file, url })
    setView('main')
  }, [])

  const clearTrack = useCallback(() => {
    if (track) URL.revokeObjectURL(track.url)
    setTrack(null)
    setView('start')
  }, [track])

  if (view === 'start') {
    return <StartScreen onStart={goToMain} onDrop={loadTrack} />
  }

  return (
    <MainScreen
      track={track}
      onBack={clearTrack}
      onLoadTrack={loadTrack}
      ozonePresetId={ozonePresetId}
      onPresetChange={setOzonePresetId}
    />
  )
}

import { useState, useEffect, useRef, useCallback } from 'react'
import type { TrackFile } from './App'
import type { OzonePresetId } from './ozonePresets'
import { useLoudness } from './useLoudness'
import { Waveform } from './Waveform'
import { OzonePresetSelector } from './OzonePresetSelector'

type Props = {
  track: TrackFile | null
  onBack: () => void
  onLoadTrack: (file: File) => void
  ozonePresetId: OzonePresetId
  onPresetChange: (id: OzonePresetId) => void
}

export function MainScreen({ track, onBack, onLoadTrack, ozonePresetId, onPresetChange }: Props) {
  const [duration, setDuration] = useState<string>('0:00')
  const [totalDuration, setTotalDuration] = useState<string>('0:00')
  const [channels, setChannels] = useState<string>('—')
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const { lufs, peakDb, sampleRate: sr, measuring, measureLoudness } = useLoudness()

  useEffect(() => {
    if (!track?.url) return
    const audio = new Audio(track.url)
    audioRef.current = audio
    const onLoadedMetadata = () => {
      const d = audio.duration
      setTotalDuration(formatTime(d))
      setChannels(audio.numberOfChannels === 2 ? 'Stereo' : 'Mono')
    }
    const onTimeUpdate = () => setDuration(formatTime(audio.currentTime))
    audio.addEventListener('loadedmetadata', onLoadedMetadata)
    audio.addEventListener('timeupdate', onTimeUpdate)
    if (audio.readyState >= 1) onLoadedMetadata()
    return () => {
      audio.removeEventListener('loadedmetadata', onLoadedMetadata)
      audio.removeEventListener('timeupdate', onTimeUpdate)
      audio.pause()
      audio.src = ''
    }
  }, [track?.url])

  useEffect(() => {
    if (!track?.file) return
    measureLoudness(track.file)
  }, [track?.file, measureLoudness])

  const togglePlay = () => {
    const a = audioRef.current
    if (!a) return
    if (a.paused) a.play()
    else a.pause()
  }

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const file = e.dataTransfer.files[0]
      if (file && file.type.startsWith('audio/')) onLoadTrack(file)
    },
    [onLoadTrack]
  )
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  if (!track) {
    return (
      <div
        style={{
          padding: 24,
          minHeight: '60vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          border: '2px dashed #444',
          borderRadius: 12,
          margin: 24,
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <button type="button" onClick={onBack}>Назад</button>
        <p style={{ marginTop: 16 }}>Перетащите аудиофайл сюда или выберите файл.</p>
        <input
          type="file"
          accept="audio/*"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onLoadTrack(f)
          }}
        />
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <button type="button" onClick={onBack} style={{ marginBottom: 16 }}>
        Назад
      </button>

      <div style={{ marginBottom: 16 }}>
        <Waveform url={track.url} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <button
          type="button"
          onClick={togglePlay}
          style={{
            width: 48,
            height: 48,
            borderRadius: '50%',
            border: 'none',
            background: '#7c4dff',
            color: '#fff',
            cursor: 'pointer',
            fontSize: 18,
          }}
        >
          ▶
        </button>
        <span>{duration}</span>
        <span>{totalDuration}</span>
      </div>

      <OzonePresetSelector selectedId={ozonePresetId} onChange={onPresetChange} />

      <div style={{ marginBottom: 24, fontSize: 14, opacity: 0.9 }}>
        <div><strong>DURATION:</strong> {totalDuration}</div>
        <div><strong>SAMPLE RATE:</strong> {sr != null ? `${(sr / 1000).toFixed(1)} kHz` : '—'}</div>
        <div><strong>CHANNELS:</strong> {channels}</div>
        <div><strong>PEAK DBFS:</strong> {peakDb != null ? `${peakDb.toFixed(1)} dB` : '—'}</div>
      </div>

      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 18, marginBottom: 8 }}>
          УРОВЕНЬ ГРОМКОСТИ <span style={{ fontWeight: 'normal', opacity: 0.8 }}>LUFS</span>
        </h2>
        <div style={{ height: 24, background: '#333', borderRadius: 4, marginBottom: 8 }} />
        {measuring ? (
          <p>Измерение уровня…</p>
        ) : (
          <p>{lufs != null ? `${lufs.toFixed(1)} LUFS` : '—'}</p>
        )}
      </section>
    </div>
  )
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

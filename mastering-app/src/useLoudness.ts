import { useState, useCallback } from 'react'

/**
 * Приближённый расчёт интегральной громкости (LUFS-подобный) по декодированному аудио.
 * Упрощённая формула: RMS по каналам, затем в dB.
 */
type LoudnessResult = { lufs: number; peakDb: number; sampleRate: number }

async function computeLoudness(file: File): Promise<LoudnessResult> {
  const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
  const buf = await file.arrayBuffer()
  const decoded = await ctx.decodeAudioData(buf)
  const numCh = decoded.numberOfChannels
  const length = decoded.length
  let sumSq = 0
  let peak = 0
  for (let ch = 0; ch < numCh; ch++) {
    const data = decoded.getChannelData(ch)
    for (let i = 0; i < length; i++) {
      const s = data[i]
      sumSq += s * s
      const abs = Math.abs(s)
      if (abs > peak) peak = abs
    }
  }
  const rms = Math.sqrt(sumSq / (numCh * length)) || 1e-10
  const lufs = 20 * Math.log10(rms)
  const peakDb = peak > 1e-10 ? 20 * Math.log10(peak) : -100
  const sampleRate = decoded.sampleRate
  ctx.close()
  return { lufs, peakDb, sampleRate }
}

export function useLoudness() {
  const [lufs, setLufs] = useState<number | null>(null)
  const [peakDb, setPeakDb] = useState<number | null>(null)
  const [sampleRate, setSampleRate] = useState<number | null>(null)
  const [measuring, setMeasuring] = useState(false)

  const measureLoudness = useCallback(async (file: File) => {
    setMeasuring(true)
    setLufs(null)
    setPeakDb(null)
    setSampleRate(null)
    try {
      const r = await computeLoudness(file)
      setLufs(r.lufs)
      setPeakDb(r.peakDb)
      setSampleRate(r.sampleRate)
    } catch {
      setLufs(null)
      setPeakDb(null)
      setSampleRate(null)
    } finally {
      setMeasuring(false)
    }
  }, [])

  return { lufs, peakDb, sampleRate, measuring, measureLoudness }
}

import { useEffect, useRef } from 'react'

type Props = { url: string }

export function Waveform({ url }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const waveRef = useRef<{ destroy: () => void } | null>(null)

  useEffect(() => {
    if (!containerRef.current || !url) return
    let cancelled = false
    import('wavesurfer.js').then(({ default: WaveSurfer }) => {
      if (cancelled || !containerRef.current) return
      waveRef.current?.destroy()
      const ws = WaveSurfer.create({
        container: containerRef.current,
        waveColor: '#26a69a',
        progressColor: '#4db6ac',
        height: 80,
        url,
      })
      waveRef.current = ws
    })
    return () => {
      cancelled = true
      waveRef.current?.destroy()
      waveRef.current = null
    }
  }, [url])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', minHeight: 80 }}
    />
  )
}

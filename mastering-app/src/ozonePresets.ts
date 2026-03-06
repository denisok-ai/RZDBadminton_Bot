const presetIds = [
  'stream',
  'edm',
  'hiphop',
  'classical',
  'podcast',
  'lofi',
  'house',
  'dry_vocal',
] as const

export type OzonePresetId = (typeof presetIds)[number]

export type OzonePreset = {
  id: OzonePresetId
  name: string
  targetLufs: number
  subtitle?: string
  badge?: string
}

export const OZONE_PRESETS: OzonePreset[] = [
  { id: 'stream', name: 'Stream', targetLufs: -14 },
  { id: 'edm', name: 'EDM', targetLufs: -9 },
  { id: 'hiphop', name: 'Hip-Hop', targetLufs: -13 },
  { id: 'classical', name: 'Classical', targetLufs: -18 },
  { id: 'podcast', name: 'Podcast', targetLufs: -16 },
  { id: 'lofi', name: 'Lo-fi', targetLufs: -18 },
  { id: 'house', name: 'House', targetLufs: -10, badge: 'EXCITER + IMAGER' },
  {
    id: 'dry_vocal',
    name: 'Dry vocal',
    targetLufs: -14,
    subtitle: 'Ровная АЧХ, камерный вокал',
  },
]


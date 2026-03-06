import type { OzonePresetId } from './ozonePresets'
import { OZONE_PRESETS } from './ozonePresets'

type Props = {
  selectedId: OzonePresetId
  onChange: (id: OzonePresetId) => void
}

export function OzonePresetSelector({ selectedId, onChange }: Props) {
  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 18, marginBottom: 8 }}>
        ПАРАМЕТРЫ · ЖАНР / СТИЛЬ
      </h2>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
          gap: 12,
        }}
      >
        {OZONE_PRESETS.map((p) => {
          const active = p.id === selectedId
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onChange(p.id)}
              style={{
                textAlign: 'left',
                padding: 12,
                borderRadius: 10,
                border: active ? '2px solid #ffb74d' : '1px solid #333',
                background: active ? '#35220f' : '#181818',
                color: '#f5f5f5',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: 72,
              }}
            >
              <div style={{ fontWeight: 600 }}>{p.name}</div>
              <div style={{ fontSize: 12, opacity: 0.9 }}>
                {p.targetLufs} LUFS
              </div>
              {p.badge && (
                <div
                  style={{
                    marginTop: 6,
                    alignSelf: 'flex-start',
                    fontSize: 10,
                    padding: '2px 6px',
                    borderRadius: 999,
                    background: '#ffb74d',
                    color: '#000',
                    fontWeight: 600,
                  }}
                >
                  {p.badge}
                </div>
              )}
              {p.subtitle && (
                <div style={{ marginTop: 4, fontSize: 11, opacity: 0.8 }}>
                  {p.subtitle}
                </div>
              )}
            </button>
          )
        })}
      </div>
    </section>
  )
}


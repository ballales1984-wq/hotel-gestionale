import { useQuery } from '@tanstack/react-query'
import { servicesApi } from '../lib/api'

const SVC_ICONS = { pernottamento: '🛏️', colazione: '☕', ristorazione: '🍽️', bar: '🍹', centro_congressi: '🎤', parcheggio: '🚗', spa: '💆', altro: '📦' }

export default function ServicesPage() {
  const { data: services, isLoading } = useQuery({
    queryKey: ['services'],
    queryFn: () => servicesApi.list().then(r => r.data),
  })

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Servizi</h1>
        <p style={{ color: 'var(--text-muted)' }}>I servizi offerti dall'hotel e le relative unità di misura</p>
      </div>
      {isLoading ? (
        <div className="loading-center"><div className="spinner" /></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {services?.map(svc => (
            <div key={svc.id} className="card" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ fontSize: 36 }}>{SVC_ICONS[svc.service_type] || '📦'}</div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>{svc.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  <code style={{ background: 'rgba(99,102,241,0.1)', padding: '1px 6px', borderRadius: 4, color: 'var(--color-primary-light)' }}>{svc.code}</code>
                  {svc.output_unit && <span style={{ marginLeft: 8 }}>· per {svc.output_unit}</span>}
                </div>
                <div style={{ marginTop: 8 }}>
                  <span className="badge badge-info">{svc.service_type}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

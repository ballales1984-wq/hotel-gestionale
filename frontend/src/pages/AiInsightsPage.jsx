import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { aiApi, authApi } from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts'

export default function AiInsightsPage() {
  const [forecastMetric, setForecastMetric] = useState('notti_vendute')
  const [forecastPeriods, setForecastPeriods] = useState(6)
  const user = useAuthStore(s => s.user)

  const hotelId = user?.hotel_id

  // Queries AI
  const { data: drivers, isLoading: loadingDrivers } = useQuery({
    queryKey: ['ai-drivers', hotelId],
    queryFn: () => aiApi.driverDiscovery(hotelId).then(r => r.data),
    enabled: !!hotelId,
  })

  const { data: forecast, isLoading: loadingForecast } = useQuery({
    queryKey: ['ai-forecast', hotelId, forecastMetric, forecastPeriods],
    queryFn: () => aiApi.forecast(hotelId, forecastMetric, forecastPeriods).then(r => r.data),
    enabled: !!hotelId,
  })

  const { data: anomalies, isLoading: loadingAnomalies } = useQuery({
    queryKey: ['ai-anomalies', hotelId],
    queryFn: () => aiApi.anomalies(hotelId).then(r => r.data),
    enabled: !!hotelId,
  })

  if (!hotelId) {
    return (
      <div className="fade-in" style={{ textAlign: 'center', marginTop: 60 }}>
        <p style={{ fontSize: 18, color: 'var(--text-muted)' }}>
          ⚠️ Il tuo account non è associato a nessun hotel. Contatta l'amministratore.
        </p>
      </div>
    )
  }

  const CustomTooltipForecast = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    const p = payload[0]
    return (
      <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--bg-border)', padding: '10px', borderRadius: 'var(--radius-sm)' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 4 }}>{label}</p>
        <p style={{ color: '#0ea5e9', fontWeight: 600 }}>Previsione: {p.value?.toFixed(0) ?? 'N/A'}</p>
        <p style={{ color: 'var(--text-muted)', fontSize: 11 }}>Range: {(p.payload?.lower_bound ?? 0).toFixed(0)} - {(p.payload?.upper_bound ?? 0).toFixed(0)}</p>
      </div>
    )
  }

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            AI Insights & Predictions
          </span>
          ✨
        </h1>
        <p style={{ color: 'var(--text-muted)' }}>Scoperta driver nascosti, rilevamento anomalie e previsioni volumetriche supportate da Machine Learning.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
        
        {/* Anomaly Detection */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700 }}>🚨 Rilevamento Anomalie Costi</h2>
            <span className="badge badge-warning">Isolation Forest</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>Identifica scostamenti anomali tra costi registrati e volumi operativi.</p>
          
          <div style={{ flex: 1, overflowY: 'auto', maxHeight: 300, paddingRight: 8 }}>
            {loadingAnomalies ? <div className="spinner" style={{ margin: 'auto', marginTop: 40 }} /> : 
              anomalies?.length > 0 ? anomalies.map((a, i) => (
                <div key={i} style={{ 
                  background: 'rgba(239,68,68,0.08)', borderLeft: '3px solid var(--color-danger)', 
                  padding: '12px', marginBottom: 12, borderRadius: '0 var(--radius-sm) var(--radius-sm) 0'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <strong style={{ fontSize: 13, color: 'var(--color-danger)' }}>Record ID: {a.record_id ?? 'N/A'}</strong>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Score: {(a.anomaly_score ?? 0).toFixed(2)}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 4 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Causa radice probabile:</span> <span className="badge badge-neutral">{a.root_cause_driver}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{a.explanation}</div>
                </div>
              )) : <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 40 }}>Nessuna anomalia rilevata.</div>
            }
          </div>
        </div>

        {/* Driver Discovery */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700 }}>🎯 Scoperta Cost Driver</h2>
            <span className="badge badge-info">LightGBM + SHAP</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>Classifica le metriche operative in base al loro reale impatto sui costi indiretti.</p>

          <div style={{ flex: 1 }}>
            {loadingDrivers ? <div className="spinner" style={{ margin: 'auto', marginTop: 40 }} /> : 
              <div style={{ height: 250 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={drivers} layout="vertical" margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.05)" />
                    <XAxis type="number" tickFormatter={v => `${v}%`} tick={{ fill: '#64748b', fontSize: 11 }} />
                    <YAxis dataKey="driver_name" type="category" tick={{ fill: '#f1f5f9', fontSize: 12 }} width={100} />
                    <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ background: 'var(--bg-elevated)', border: 'none', borderRadius: 8 }} />
                    <Bar dataKey="importance_pct" fill="#6366f1" radius={[0, 4, 4, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            }
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
              <strong>Explainability:</strong> I driver con la barra più lunga hanno il maggior peso (SHAP value) nell'aumento dell'overhead.
            </div>
          </div>
        </div>

      </div>

      {/* Forecasting */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700 }}>📈 Previsioni Operative (Forecasting)</h2>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>Utilizza serie storiche per prevedere la domanda futura.</p>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <select value={forecastMetric} onChange={e => setForecastMetric(e.target.value)} className="btn btn-secondary btn-sm">
              <option value="notti_vendute">Notti Vendute</option>
              <option value="coperti">Coperti</option>
              <option value="ore_lavorate">Ore Lavorate (Totali)</option>
            </select>
            <select value={forecastPeriods} onChange={e => setForecastPeriods(Number(e.target.value))} className="btn btn-secondary btn-sm">
              <option value={3}>3 Mesi</option>
              <option value={6}>6 Mesi</option>
              <option value={12}>12 Mesi</option>
            </select>
          </div>
        </div>

        {loadingForecast ? <div className="loading-center"><div className="spinner" /></div> : (
          <div style={{ height: 350 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecast} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
                <Tooltip content={<CustomTooltipForecast />} />
                {/* Visualizziamo il lower e upper bound come area o linee tratteggiate */}
                <Line type="monotone" dataKey="upper_bound" stroke="rgba(14,165,233,0.2)" strokeDasharray="5 5" dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="lower_bound" stroke="rgba(14,165,233,0.2)" strokeDasharray="5 5" dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="predicted_value" stroke="#0ea5e9" strokeWidth={3} dot={{ r: 4, fill: '#0ea5e9', strokeWidth: 2, stroke: '#1a1a2e' }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

    </div>
  )
}

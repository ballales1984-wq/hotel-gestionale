import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { simulationApi, periodsApi } from '../lib/api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'

function fmt(n) {
  if (!n && n !== 0) return '—'
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--bg-border)', borderRadius: 'var(--radius-sm)', padding: '12px 16px' }}>
      <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => <p key={i} style={{ color: p.color, fontSize: 13, fontWeight: 600 }}>{p.name}: {fmt(p.value)}</p>)}
    </div>
  )
}

export default function SimulationPage() {
  const [selectedPeriod, setSelectedPeriod] = useState('')
  const [scenarioName, setScenarioName] = useState('Scenario personalizzato')
  const [laborReduction, setLaborReduction] = useState(0)
  const [overheadReduction, setOverheadReduction] = useState(0)
  const [result, setResult] = useState(null)

  const { data: periods } = useQuery({
    queryKey: ['periods'],
    queryFn: () => periodsApi.list().then(r => r.data),
  })

  const { data: templates } = useQuery({
    queryKey: ['sim-templates'],
    queryFn: () => simulationApi.templates().then(r => r.data),
  })

  const simMutation = useMutation({
    mutationFn: () => simulationApi.run(selectedPeriod, {
      name: scenarioName,
      labor_reduction_pct: laborReduction > 0 ? laborReduction : null,
      overhead_reduction_pct: overheadReduction > 0 ? overheadReduction : null,
      revenue_changes: [],
      outsourcing: [],
    }),
    onSuccess: (res) => {
      setResult(res.data)
      toast.success('Simulazione completata')
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore simulazione'),
  })

  const chartData = result?.services?.map(s => ({
    name: s.service_name,
    'Margine Baseline': Number(s.baseline_margin),
    'Margine Scenario': Number(s.scenario_margin),
    delta: Number(s.margin_delta),
  })) || []

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Simulazioni What-If</h1>
        <p style={{ color: 'var(--text-muted)' }}>Analizza l'impatto di decisioni strategiche sui margini</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: 24 }}>
        {/* Pannello configurazione */}
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>⚙️ Parametri Scenario</div>

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label>Periodo</label>
              <select value={selectedPeriod} onChange={e => setSelectedPeriod(e.target.value)}>
                <option value="">— Seleziona —</option>
                {periods?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label>Nome Scenario</label>
              <input value={scenarioName} onChange={e => setScenarioName(e.target.value)} />
            </div>

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label>Riduzione costo personale: <strong style={{ color: 'var(--color-primary-light)' }}>{laborReduction}%</strong></label>
              <input
                type="range" min={0} max={30} step={1}
                value={laborReduction}
                onChange={e => setLaborReduction(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--color-primary)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)' }}>
                <span>0%</span><span>15%</span><span>30%</span>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 20 }}>
              <label>Riduzione overhead: <strong style={{ color: '#0ea5e9' }}>{overheadReduction}%</strong></label>
              <input
                type="range" min={0} max={30} step={1}
                value={overheadReduction}
                onChange={e => setOverheadReduction(Number(e.target.value))}
                style={{ width: '100%', accentColor: '#0ea5e9' }}
              />
            </div>

            <button
              className="btn btn-primary"
              onClick={() => simMutation.mutate()}
              disabled={!selectedPeriod || simMutation.isPending}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {simMutation.isPending ? '⏳ Calcolo...' : '🎯 Esegui Simulazione'}
            </button>
          </div>

          {/* Template scenari */}
          {templates && (
            <div className="card">
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>📋 Template Rapidi</div>
              {templates.map((t, i) => (
                <div key={i} style={{
                  padding: '10px 12px', marginBottom: 8,
                  background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer', transition: 'background var(--transition-fast)',
                }}
                  onClick={() => {
                    setScenarioName(t.name)
                    if (t.scenario.labor_reduction_pct) setLaborReduction(Number(t.scenario.labor_reduction_pct))
                    if (t.scenario.overhead_reduction_pct) setOverheadReduction(Number(t.scenario.overhead_reduction_pct))
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{t.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{t.description}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Risultati */}
        <div>
          {result ? (
            <>
              {/* Summary */}
              <div className="alert alert-info" style={{ marginBottom: 20 }}>
                📊 {result.summary}
              </div>

              <div className="kpi-grid" style={{ marginBottom: 24 }}>
                {[
                  { l: 'Risparmio Costi', v: fmt(result.total_cost_saving), c: result.total_cost_saving >= 0 ? '#10b981' : '#ef4444' },
                  { l: 'Miglioramento Margine', v: fmt(result.margin_improvement), c: result.margin_improvement >= 0 ? '#10b981' : '#ef4444' },
                ].map(item => (
                  <div key={item.l} className="kpi-card">
                    <div className="kpi-label">{item.l}</div>
                    <div className="kpi-value" style={{ color: item.c }}>{item.v}</div>
                  </div>
                ))}
              </div>

              {/* Grafico comparativo */}
              <div className="chart-card" style={{ marginBottom: 20 }}>
                <div className="chart-title">Margine Baseline vs Scenario</div>
                <div className="chart-subtitle">Confronto per servizio</div>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="Margine Baseline" fill="#4f46e5" radius={[4,4,0,0]} />
                    <Bar dataKey="Margine Scenario" fill="#10b981" radius={[4,4,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Tabella dettaglio */}
              <div className="table-card">
                <div className="table-header">
                  <div className="table-title">Dettaglio per Servizio</div>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Servizio</th>
                      <th style={{ textAlign: 'right' }}>Costo Baseline</th>
                      <th style={{ textAlign: 'right' }}>Costo Scenario</th>
                      <th style={{ textAlign: 'right' }}>Δ Costo</th>
                      <th style={{ textAlign: 'right' }}>Margine Baseline</th>
                      <th style={{ textAlign: 'right' }}>Margine Scenario</th>
                      <th style={{ textAlign: 'right' }}>Δ Margine</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.services?.map(s => (
                      <tr key={s.service_id}>
                        <td><strong>{s.service_name}</strong></td>
                        <td style={{ textAlign: 'right' }}>{fmt(s.baseline_cost)}</td>
                        <td style={{ textAlign: 'right' }}>{fmt(s.scenario_cost)}</td>
                        <td style={{ textAlign: 'right' }}>
                          <span className={`currency ${Number(s.cost_delta) <= 0 ? 'positive' : 'negative'}`}>
                            {Number(s.cost_delta) <= 0 ? '' : '+'}{fmt(s.cost_delta)}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>{fmt(s.baseline_margin)}</td>
                        <td style={{ textAlign: 'right' }}>{fmt(s.scenario_margin)}</td>
                        <td style={{ textAlign: 'right' }}>
                          <span className={`currency ${Number(s.margin_delta) >= 0 ? 'positive' : 'negative'}`}>
                            {Number(s.margin_delta) >= 0 ? '+' : ''}{fmt(s.margin_delta)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: 300, flexDirection: 'column', gap: 16,
              background: 'var(--gradient-card)', borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--bg-border)',
            }}>
              <span style={{ fontSize: 48 }}>🎯</span>
              <div style={{ color: 'var(--text-muted)', textAlign: 'center' }}>
                <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Configura e avvia la simulazione</div>
                <div style={{ fontSize: 14 }}>Seleziona un periodo e imposta i parametri dello scenario</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

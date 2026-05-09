import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, ResponsiveContainer, Legend,
} from 'recharts'
import { reportsApi, periodsApi } from '../lib/api'

const COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

function fmt(n) {
  if (!n && n !== 0) return '—'
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
}

function fmtPct(n) {
  if (!n && n !== 0) return '—'
  return `${Number(n).toFixed(1)}%`
}

function KpiCard({ icon, label, value, sub, color }) {
  return (
    <div className="kpi-card">
      <div className="kpi-icon" style={{ background: `${color}20` }}>
        <span style={{ fontSize: 22 }}>{icon}</span>
      </div>
      <div>
        <div className="kpi-label">{label}</div>
        <div className="kpi-value" style={{ color }}>{value}</div>
        {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
      </div>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--bg-border)',
      borderRadius: 'var(--radius-sm)', padding: '12px 16px',
    }}>
      <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontSize: 13, fontWeight: 600 }}>
          {p.name}: {fmt(p.value)}
        </p>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { data: periods } = useQuery({
    queryKey: ['periods'],
    queryFn: () => periodsApi.list().then(r => r.data),
  })

  const latestPeriod = periods?.[0]

  const { data: kpi, isLoading: kpiLoading } = useQuery({
    queryKey: ['kpi', latestPeriod?.id],
    queryFn: () => reportsApi.kpi(latestPeriod?.id).then(r => r.data),
    enabled: !!latestPeriod?.id,
  })

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ['report', latestPeriod?.id],
    queryFn: () => reportsApi.get(latestPeriod?.id).then(r => r.data),
    enabled: !!latestPeriod?.id,
  })

  const isLoading = kpiLoading || reportLoading

  if (!latestPeriod) {
    return (
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 8 }}>Dashboard</h1>
        <div className="alert alert-info" style={{ marginTop: 24 }}>
          ℹ️ Nessun periodo configurato. Vai in <strong>Periodi</strong> per creare il primo periodo contabile.
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="loading-center">
        <div className="spinner" />
        <span style={{ color: 'var(--text-muted)' }}>Caricamento dati...</span>
      </div>
    )
  }

  if (!kpi) {
    return (
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 8 }}>Dashboard</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
          Periodo: <strong>{latestPeriod.name}</strong>
        </p>
        <div className="alert alert-warning">
          ⚠️ Nessun risultato ABC per questo periodo. Vai in <strong>Calcolo ABC</strong> per eseguire il calcolo.
        </div>
      </div>
    )
  }

  const services = report?.services || []
  const overallMarginPct = kpi?.overall_margin_pct
  const laborPct = kpi?.labor_cost_incidence_pct

  // Dati per i grafici
  const barData = services.map(s => ({
    name: s.service_name,
    Ricavi: Number(s.revenue),
    Costi: Number(s.total_cost),
    Margine: Number(s.gross_margin),
  }))

  const pieData = services.map(s => ({
    name: s.service_name,
    value: Math.abs(Number(s.total_cost)),
  }))

  return (
    <div className="fade-in">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>
            Dashboard Direzionale
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>
            Periodo: <strong style={{ color: 'var(--text-secondary)' }}>{latestPeriod.name}</strong>
          </p>
        </div>
        <span className="badge badge-info">Aggiornato</span>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <KpiCard
          icon="💰"
          label="Ricavi Totali"
          value={fmt(kpi.total_revenue)}
          color="#0ea5e9"
        />
        <KpiCard
          icon="📉"
          label="Costi Totali"
          value={fmt(kpi.total_cost)}
          color="#94a3b8"
        />
        <KpiCard
          icon="📈"
          label="Margine Lordo"
          value={fmt(kpi.total_margin)}
          sub={overallMarginPct ? `${fmtPct(overallMarginPct)} sui ricavi` : null}
          color={kpi.total_margin >= 0 ? '#10b981' : '#ef4444'}
        />
        <KpiCard
          icon="👥"
          label="Incidenza Personale"
          value={laborPct ? fmtPct(laborPct) : '—'}
          sub="sul totale costi"
          color="#f59e0b"
        />
      </div>

      {/* Charts */}
      <div className="charts-grid">
        {/* Ricavi vs Costi per servizio */}
        <div className="chart-card">
          <div className="chart-title">Ricavi vs Costi per Servizio</div>
          <div className="chart-subtitle">Confronto ricavi, costi e margine</div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} margin={{ top: 0, right: 0, bottom: 20, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="name"
                tick={{ fill: '#64748b', fontSize: 11 }}
                angle={-30}
                textAnchor="end"
                interval={0}
              />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ color: 'var(--text-secondary)', fontSize: 12, paddingTop: 12 }} />
              <Bar dataKey="Ricavi" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Costi" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Margine" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Distribuzione costi */}
        <div className="chart-card">
          <div className="chart-title">Distribuzione Costi per Servizio</div>
          <div className="chart-subtitle">Quota di costo assorbita da ogni servizio</div>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {pieData.map((entry, index) => (
                  <Cell key={index} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => fmt(v)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tabella servizi */}
      <div className="table-card">
        <div className="table-header">
          <div className="table-title">Redditività per Servizio</div>
          <span className="badge badge-neutral">{services.length} servizi</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Servizio</th>
              <th style={{ textAlign: 'right' }}>Ricavi</th>
              <th style={{ textAlign: 'right' }}>Costi Totali</th>
              <th style={{ textAlign: 'right' }}>Margine Lordo</th>
              <th style={{ textAlign: 'right' }}>Margine %</th>
              <th style={{ textAlign: 'right' }}>Costo unitario</th>
              <th>Performance</th>
            </tr>
          </thead>
          <tbody>
            {services.map(svc => {
              const isPositive = Number(svc.gross_margin) >= 0
              const marginPct = Number(svc.margin_pct) || 0
              const barWidth = Math.min(Math.abs(marginPct), 100)
              return (
                <tr key={svc.service_id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{svc.service_name}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{svc.service_type}</div>
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {fmt(svc.revenue)}
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {fmt(svc.total_cost)}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <span className={`currency ${isPositive ? 'positive' : 'negative'}`}>
                      {fmt(svc.gross_margin)}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <span className={isPositive ? 'badge badge-success' : 'badge badge-danger'}>
                      {fmtPct(svc.margin_pct)}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>
                    {svc.cost_per_unit
                      ? `${fmt(svc.cost_per_unit)} /${svc.output_unit || 'u'}`
                      : '—'}
                  </td>
                  <td style={{ minWidth: 120 }}>
                    <div className="margin-bar">
                      <div
                        className={`margin-bar-fill ${isPositive ? 'positive' : 'negative'}`}
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                      {isPositive ? '✓ In utile' : '✗ In perdita'}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Avvisi */}
      {report?.warnings?.length > 0 && (
        <div style={{ marginTop: 20 }}>
          {report.warnings.map((w, i) => (
            <div key={i} className="alert alert-warning" style={{ marginBottom: 8 }}>
              ⚠️ {w}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

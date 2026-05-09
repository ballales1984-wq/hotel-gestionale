import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { periodsApi, reportsApi } from '../lib/api'
import toast from 'react-hot-toast'

function fmt(n) {
  if (!n && n !== 0) return '—'
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
}

export default function ABCReportPage() {
  const [selectedPeriod, setSelectedPeriod] = useState(null)
  const qc = useQueryClient()

  const { data: periods } = useQuery({
    queryKey: ['periods'],
    queryFn: () => periodsApi.list().then(r => r.data),
  })

  const { data: report, isLoading: loading } = useQuery({
    queryKey: ['report', selectedPeriod],
    queryFn: () => reportsApi.get(selectedPeriod).then(r => r.data),
    enabled: !!selectedPeriod,
  })

  const calcMutation = useMutation({
    mutationFn: () => reportsApi.calculate(selectedPeriod),
    onSuccess: (res) => {
      toast.success('Calcolo ABC completato!')
      qc.invalidateQueries({ queryKey: ['report', selectedPeriod] })
      qc.invalidateQueries({ queryKey: ['kpi', selectedPeriod] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore nel calcolo'),
  })

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Calcolo ABC</h1>
          <p style={{ color: 'var(--text-muted)' }}>Avvia o visualizza il calcolo Activity-Based Costing per un periodo</p>
        </div>
      </div>

      {/* Selezione periodo */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Seleziona Periodo</label>
            <select value={selectedPeriod || ''} onChange={e => setSelectedPeriod(e.target.value)}>
              <option value="">— Seleziona un periodo —</option>
              {periods?.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => calcMutation.mutate()}
            disabled={!selectedPeriod || calcMutation.isPending}
            style={{ height: 42 }}
          >
            {calcMutation.isPending ? '⏳ Calcolo in corso...' : '🧮 Esegui Calcolo ABC'}
          </button>
        </div>
      </div>

      {/* Risultati */}
      {loading && (
        <div className="loading-center">
          <div className="spinner" />
          <span style={{ color: 'var(--text-muted)' }}>Caricamento risultati...</span>
        </div>
      )}

      {report && !loading && (
        <>
          {/* Summary */}
          <div className="kpi-grid" style={{ marginBottom: 24 }}>
            {[
              { l: 'Ricavi Totali', v: fmt(report.total_revenue), c: '#0ea5e9' },
              { l: 'Costi Totali', v: fmt(report.total_cost), c: '#94a3b8' },
              { l: 'Margine Totale', v: fmt(report.total_margin), c: report.total_margin >= 0 ? '#10b981' : '#ef4444' },
              { l: 'Non Allocato', v: fmt(report.unallocated_amount), c: '#f59e0b' },
            ].map(item => (
              <div key={item.l} className="kpi-card">
                <div className="kpi-label">{item.l}</div>
                <div className="kpi-value" style={{ fontSize: 22, color: item.c }}>{item.v}</div>
              </div>
            ))}
          </div>

          {/* Tabella dettaglio */}
          <div className="table-card">
            <div className="table-header">
              <div className="table-title">Dettaglio per Servizio</div>
              <span className="badge badge-neutral">Iterazioni: {report.iterations_used}</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Servizio</th>
                  <th style={{ textAlign: 'right' }}>Costi Diretti</th>
                  <th style={{ textAlign: 'right' }}>Costi Personale</th>
                  <th style={{ textAlign: 'right' }}>Overhead</th>
                  <th style={{ textAlign: 'right' }}>Costo Totale</th>
                  <th style={{ textAlign: 'right' }}>Ricavi</th>
                  <th style={{ textAlign: 'right' }}>Margine</th>
                  <th style={{ textAlign: 'right' }}>Margine %</th>
                </tr>
              </thead>
              <tbody>
                {report.services?.map(svc => (
                  <tr key={svc.service_id}>
                    <td><strong>{svc.service_name}</strong></td>
                    <td style={{ textAlign: 'right' }}>{fmt(svc.direct_cost)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(svc.labor_cost)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(svc.overhead_cost)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>{fmt(svc.total_cost)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(svc.revenue)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <span className={`currency ${Number(svc.gross_margin) >= 0 ? 'positive' : 'negative'}`}>
                        {fmt(svc.gross_margin)}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <span className={Number(svc.margin_pct) >= 0 ? 'badge badge-success' : 'badge badge-danger'}>
                        {svc.margin_pct ? `${Number(svc.margin_pct).toFixed(1)}%` : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {report.warnings?.length > 0 && (
            <div style={{ marginTop: 16 }}>
              {report.warnings.map((w, i) => (
                <div key={i} className="alert alert-warning" style={{ marginBottom: 8 }}>⚠️ {w}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

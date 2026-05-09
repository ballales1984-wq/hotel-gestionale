import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { allocationsApi } from '../lib/api'
import { useState } from 'react'
import toast from 'react-hot-toast'

const LEVEL_LABELS = {
  costo_ad_attivita: 'Costo → Attività',
  attivita_a_servizio: 'Attività → Servizio',
  attivita_ad_attivita: 'Attività → Attività',
}

const LEVEL_COLORS = {
  costo_ad_attivita: 'badge-info',
  attivita_a_servizio: 'badge-success',
  attivita_ad_attivita: 'badge-warning',
}

export default function AllocationsPage() {
  const qc = useQueryClient()

  const { data: rules, isLoading } = useQuery({
    queryKey: ['allocations'],
    queryFn: () => allocationsApi.list().then(r => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => allocationsApi.delete(id),
    onSuccess: () => { toast.success('Regola disattivata'); qc.invalidateQueries({ queryKey: ['allocations'] }) },
  })

  // Raggruppa per livello
  const grouped = rules?.reduce((acc, r) => {
    acc[r.level] = [...(acc[r.level] || []), r]
    return acc
  }, {}) || {}

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Regole di Allocazione</h1>
        <p style={{ color: 'var(--text-muted)' }}>Definisci come i costi fluiscono nel modello ABC</p>
      </div>

      <div className="alert alert-info" style={{ marginBottom: 24 }}>
        ℹ️ Le regole di allocazione definiscono la logica ABC su 3 livelli: <strong>Costi → Attività → Servizi</strong>.
        Le regole con % fissa vengono applicate direttamente; quelle con driver vengono calcolate proporzionalmente.
      </div>

      {isLoading ? <div className="loading-center"><div className="spinner" /></div> : (
        Object.entries(LEVEL_LABELS).map(([level, label]) => {
          const levelRules = grouped[level] || []
          return (
            <div key={level} style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700 }}>{label}</h3>
                <span className={`badge ${LEVEL_COLORS[level]}`}>{levelRules.length} regole</span>
              </div>
              <div className="table-card">
                <table>
                  <thead>
                    <tr>
                      <th>Nome Regola</th>
                      <th style={{ textAlign: 'right' }}>% Allocazione</th>
                      <th>Priorità</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {levelRules.length === 0 ? (
                      <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>Nessuna regola configurata</td></tr>
                    ) : levelRules.map(r => (
                      <tr key={r.id}>
                        <td style={{ fontWeight: 500 }}>{r.name}</td>
                        <td style={{ textAlign: 'right' }}>
                          {r.allocation_pct
                            ? <strong>{(Number(r.allocation_pct) * 100).toFixed(1)}%</strong>
                            : <span className="badge badge-neutral">Da driver</span>}
                        </td>
                        <td><span className="badge badge-neutral">P{r.priority}</span></td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn-danger btn-sm" onClick={() => deleteMutation.mutate(r.id)}>Disattiva</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}

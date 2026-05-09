import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { activitiesApi } from '../lib/api'
import toast from 'react-hot-toast'

const DEPARTMENTS = [
  { v: 'reception', l: 'Reception' }, { v: 'housekeeping', l: 'Housekeeping' },
  { v: 'food_beverage', l: 'Food & Beverage' }, { v: 'manutenzione', l: 'Manutenzione' },
  { v: 'commerciale', l: 'Commerciale' }, { v: 'congressi', l: 'Congressi' },
  { v: 'direzione', l: 'Direzione' }, { v: 'amministrazione', l: 'Amministrazione' },
]

const DEPT_ICONS = { reception: '🛎️', housekeeping: '🧹', food_beverage: '🍽️', manutenzione: '🔧', commerciale: '📢', congressi: '🎤', direzione: '👔', amministrazione: '📋' }

export default function ActivitiesPage() {
  const [filterDept, setFilterDept] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ code: '', name: '', department: 'reception', is_support_activity: false })
  const qc = useQueryClient()

  const { data: activities, isLoading } = useQuery({
    queryKey: ['activities', filterDept],
    queryFn: () => activitiesApi.list(filterDept || undefined).then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: () => activitiesApi.create(form),
    onSuccess: () => {
      toast.success('Attività creata')
      setShowForm(false)
      setForm({ code: '', name: '', department: 'reception', is_support_activity: false })
      qc.invalidateQueries({ queryKey: ['activities'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => activitiesApi.delete(id),
    onSuccess: () => { toast.success('Attività disattivata'); qc.invalidateQueries({ queryKey: ['activities'] }) },
  })

  const grouped = activities?.reduce((acc, a) => {
    acc[a.department] = [...(acc[a.department] || []), a]
    return acc
  }, {}) || {}

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Attività Operative</h1>
          <p style={{ color: 'var(--text-muted)' }}>{activities?.length || 0} attività configurate</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '✕ Chiudi' : '+ Nuova Attività'}
        </button>
      </div>

      {/* Form nuova attività */}
      {showForm && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>➕ Nuova Attività</div>
          <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr 200px auto auto', gap: 12, alignItems: 'flex-end' }}>
            <div className="form-group">
              <label>Codice</label>
              <input value={form.code} onChange={e => setForm({...form, code: e.target.value})} placeholder="REC-001" />
            </div>
            <div className="form-group">
              <label>Nome</label>
              <input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Check-in / Check-out" />
            </div>
            <div className="form-group">
              <label>Reparto</label>
              <select value={form.department} onChange={e => setForm({...form, department: e.target.value})}>
                {DEPARTMENTS.map(d => <option key={d.v} value={d.v}>{d.l}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingBottom: 2 }}>
              <input type="checkbox" id="support" checked={form.is_support_activity} onChange={e => setForm({...form, is_support_activity: e.target.checked})} style={{ width: 16, height: 16 }} />
              <label htmlFor="support" style={{ fontSize: 12, margin: 0 }}>Supporto</label>
            </div>
            <button className="btn btn-primary" onClick={() => createMutation.mutate()} disabled={!form.code || !form.name}>
              Crea
            </button>
          </div>
        </div>
      )}

      {/* Filtro reparto */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <button className={`btn ${!filterDept ? 'btn-primary' : 'btn-secondary'} btn-sm`} onClick={() => setFilterDept('')}>
          Tutti
        </button>
        {DEPARTMENTS.map(d => (
          <button key={d.v} className={`btn ${filterDept === d.v ? 'btn-primary' : 'btn-secondary'} btn-sm`} onClick={() => setFilterDept(d.v)}>
            {DEPT_ICONS[d.v]} {d.l}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="loading-center"><div className="spinner" /></div>
      ) : (
        Object.entries(grouped).map(([dept, acts]) => (
          <div key={dept} style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{ fontSize: 20 }}>{DEPT_ICONS[dept]}</span>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)' }}>
                {DEPARTMENTS.find(d => d.v === dept)?.l || dept}
              </h3>
              <span className="badge badge-neutral" style={{ marginLeft: 4 }}>{acts.length}</span>
            </div>
            <div className="table-card">
              <table>
                <thead>
                  <tr>
                    <th>Codice</th>
                    <th>Nome</th>
                    <th>Tipo</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {acts.map(act => (
                    <tr key={act.id}>
                      <td><code style={{ fontSize: 12, color: 'var(--color-primary-light)', background: 'rgba(99,102,241,0.1)', padding: '2px 8px', borderRadius: 4 }}>{act.code}</code></td>
                      <td style={{ fontWeight: 500 }}>{act.name}</td>
                      <td>
                        {act.is_support_activity
                          ? <span className="badge badge-warning">Supporto</span>
                          : <span className="badge badge-info">Primaria</span>}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-danger btn-sm" onClick={() => deleteMutation.mutate(act.id)}>Disattiva</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  )
}

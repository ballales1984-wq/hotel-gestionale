import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { costDriversApi } from '../lib/api'
import toast from 'react-hot-toast'

const DRIVER_TYPES = [
  { v: 'volume', l: 'Volume (n° transazioni, coperti, stanze)' },
  { v: 'time', l: 'Tempo (ore, minuti)' },
  { v: 'area', l: 'Area (metri quadrati)' },
  { v: 'percentage', l: 'Percentuale fissa' },
  { v: 'composite', l: 'Composito (mix)' },
]

export default function CostDriversPage() {
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({ name: '', code: '', driver_type: 'volume', unit: '', description: '' })
  const qc = useQueryClient()

  const { data: drivers = [], isLoading } = useQuery({
    queryKey: ['cost-drivers'],
    queryFn: () => costDriversApi.list().then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: () => costDriversApi.create(form),
    onSuccess: () => {
      toast.success('Driver creato')
      setShowForm(false)
      resetForm()
      qc.invalidateQueries({ queryKey: ['cost-drivers'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore'),
  })

  const updateMutation = useMutation({
    mutationFn: () => costDriversApi.update(editingId, form),
    onSuccess: () => {
      toast.success('Driver aggiornato')
      setShowForm(false)
      setEditingId(null)
      resetForm()
      qc.invalidateQueries({ queryKey: ['cost-drivers'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => costDriversApi.delete(id),
    onSuccess: () => {
      toast.success('Driver disattivato')
      qc.invalidateQueries({ queryKey: ['cost-drivers'] })
    },
  })

  const resetForm = () => {
    setForm({ name: '', code: '', driver_type: 'volume', unit: '', description: '' })
    setEditingId(null)
  }

  const openEdit = (drv) => {
    setEditingId(drv.id)
    setForm({
      name: drv.name,
      code: drv.code,
      driver_type: drv.driver_type,
      unit: drv.unit,
      description: drv.description || '',
    })
    setShowForm(true)
  }

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Configurazione Driver</h1>
          <p style={{ color: 'var(--text-muted)' }}>{drivers.length} driver definiti</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(!showForm) }}>
          {showForm ? '✕ Chiudi' : '+ Nuovo Driver'}
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
            {editingId ? '✏️ Modifica Driver' : '➕ Nuovo Driver di Allocazione'}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '200px 150px 1fr 150px auto', gap: 12, alignItems: 'flex-end' }}>
            <div className="form-group">
              <label>Nome</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Ore Lavorate" />
            </div>
            <div className="form-group">
              <label>Codice</label>
              <input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} placeholder="DRV-ORE" />
            </div>
            <div className="form-group">
              <label>Tipo</label>
              <select value={form.driver_type} onChange={e => setForm({ ...form, driver_type: e.target.value })}>
                {DRIVER_TYPES.map(d => <option key={d.v} value={d.v}>{d.l}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Unità</label>
              <input value={form.unit} onChange={e => setForm({ ...form, unit: e.target.value })} placeholder="ore" />
            </div>
            <button
              className="btn btn-primary"
              onClick={() => editingId ? updateMutation.mutate() : createMutation.mutate()}
              disabled={!form.name || !form.code || !form.unit}
            >
              {editingId ? 'Aggiorna' : 'Crea'}
            </button>
          </div>
          <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Descrizione (opzionale)</label>
              <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Descrizione del driver" />
            </div>
          </div>
        </div>
      )}

      {/* Lista driver */}
      {isLoading ? <div className="spinner" style={{ margin: 'auto', marginTop: 40 }} /> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {drivers.map(drv => (
            <div key={drv.id} className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--color-primary)' }}>{drv.code}</div>
                  <div style={{ fontSize: 15, marginTop: 2 }}>{drv.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                    Tipo: <span style={{ textTransform: 'capitalize' }}>{drv.driver_type}</span> • Unità: {drv.unit}
                  </div>
                  {drv.description && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{drv.description}</div>}
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => openEdit(drv)}>Modifica</button>
                  <button className="btn btn-danger btn-sm" onClick={() => { if (confirm('Disattivare?')) deleteMutation.mutate(drv.id) }}>
                    Elimina
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {drivers.length === 0 && !isLoading && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 60 }}>
          Nessun driver configurato. Creane uno nuovo per iniziare.
        </div>
      )}
    </div>
  )
}

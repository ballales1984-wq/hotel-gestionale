import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { costCentersApi } from '../lib/api'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

const DEPARTMENTS = [
  { v: 'reception', l: 'Reception' }, { v: 'housekeeping', l: 'Housekeeping' },
  { v: 'food_beverage', l: 'Food & Beverage' }, { v: 'manutenzione', l: 'Manutenzione' },
  { v: 'commerciale', l: 'Commerciale' }, { v: 'congressi', l: 'Congressi' },
  { v: 'direzione', l: 'Direzione' }, { v: 'amministrazione', l: 'Amministrazione' },
]

export default function CostCentersPage() {
  const user = useAuthStore(s => s.user)
  const hotelId = user?.hotel_id

  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({ code: '', name: '', department: 'reception', parent_id: '', description: '' })
  const qc = useQueryClient()

  const { data: centers = [], isLoading } = useQuery({
    queryKey: ['cost-centers', hotelId],
    queryFn: () => costCentersApi.list(hotelId).then(r => r.data),
    enabled: !!hotelId,
  })

  const createMutation = useMutation({
    mutationFn: () => costCentersApi.create({
      ...form,
      hotel_id: hotelId,
      parent_id: form.parent_id || null,
    }),
    onSuccess: () => {
      toast.success('Centro di costo creato')
      setShowForm(false)
      resetForm()
      qc.invalidateQueries({ queryKey: ['cost-centers', hotelId] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore'),
  })

  const updateMutation = useMutation({
    mutationFn: () => costCentersApi.update(editingId, {
      ...form,
      parent_id: form.parent_id || null,
    }),
    onSuccess: () => {
      toast.success('Centro di costo aggiornato')
      setShowForm(false)
      setEditingId(null)
      resetForm()
      qc.invalidateQueries({ queryKey: ['cost-centers', hotelId] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => costCentersApi.delete(id),
    onSuccess: () => {
      toast.success('Centro di costo disattivato')
      qc.invalidateQueries({ queryKey: ['cost-centers', hotelId] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: () => costCentersApi.update(editingId, {
      ...form,
      parent_id: form.parent_id || null,
    }),
    onSuccess: () => {
      toast.success('Centro di costo aggiornato')
      setShowForm(false)
      setEditingId(null)
      resetForm()
      qc.invalidateQueries({ queryKey: ['cost-centers'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => costCentersApi.delete(id),
    onSuccess: () => {
      toast.success('Centro di costo disattivato')
      qc.invalidateQueries({ queryKey: ['cost-centers'] })
    },
  })

  const resetForm = () => {
    setForm({ code: '', name: '', department: 'reception', parent_id: '', description: '' })
    setEditingId(null)
  }

  const openEdit = (cc) => {
    setEditingId(cc.id)
    setForm({
      code: cc.code,
      name: cc.name,
      department: cc.department,
      parent_id: cc.parent_id || '',
      description: cc.description || '',
    })
    setShowForm(true)
  }

  const grouped = centers.reduce((acc, cc) => {
    const dept = cc.department
    acc[dept] = acc[dept] || []
    acc[dept].push(cc)
    return acc
  }, {})

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Centri di Costo</h1>
          <p style={{ color: 'var(--text-muted)' }}>{centers.length} centri configurati</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(!showForm) }}>
          {showForm ? '✕ Chiudi' : '+ Nuovo Centro'}
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
            {editingId ? '✏️ Modifica Centro' : '➕ Nuovo Centro di Costo'}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr 200px 1fr auto', gap: 12, alignItems: 'flex-end' }}>
            <div className="form-group">
              <label>Codice</label>
              <input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} placeholder="CC-REC" />
            </div>
            <div className="form-group">
              <label>Nome</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Reception" />
            </div>
            <div className="form-group">
              <label>Reparto</label>
              <select value={form.department} onChange={e => setForm({ ...form, department: e.target.value })}>
                {DEPARTMENTS.map(d => <option key={d.v} value={d.v}>{d.l}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Centro Padre (opz.)</label>
              <select value={form.parent_id} onChange={e => setForm({ ...form, parent_id: e.target.value })}>
                <option value="">— Nessuno —</option>
                {centers
                  .filter(c => c.id !== editingId)
                  .map(c => <option key={c.id} value={c.id}>{c.code} – {c.name}</option>)}
              </select>
            </div>
            <button
              className="btn btn-primary"
              onClick={() => editingId ? updateMutation.mutate() : createMutation.mutate()}
              disabled={!hotelId || (!editingId && (!form.code || !form.name))}
            >
              {editingId ? 'Aggiorna' : 'Crea'}
            </button>
          </div>
        </div>
      )}

      {/* Filtri reparto */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {Object.keys(grouped).length === 0 && <span style={{ color: 'var(--text-muted)' }}>Nessun centro di costo. Creane uno nuovo.</span>}
      </div>

      {/* Lista raggruppata per reparto */}
      {Object.entries(grouped).map(([dept, list]) => (
        <div key={dept} style={{ marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, textTransform: 'capitalize' }}>
            {DEPARTMENTS.find(d => d.v === dept)?.l || dept}
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
            {list.map(cc => (
              <div key={cc.id} className="card" style={{ padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 15 }}>{cc.code}</div>
                    <div style={{ color: 'var(--text-primary)' }}>{cc.name}</div>
                    {cc.parent_id && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Padre: {cc.parent_id}</div>}
                    {cc.description && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{cc.description}</div>}
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-secondary btn-sm" onClick={() => openEdit(cc)}>Modifica</button>
                    <button className="btn btn-danger btn-sm" onClick={() => { if (confirm('Disattivare?')) deleteMutation.mutate(cc.id) }}>
                      Elimina
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

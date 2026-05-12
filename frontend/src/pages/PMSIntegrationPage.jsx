import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pmsIntegrationsApi } from '../lib/api'
import toast from 'react-hot-toast'

const SYSTEM_TYPES = [
  { v: 'pms_csv', l: 'PMS - CSV' },
  { v: 'pms_api', l: 'PMS - API' },
  { v: 'erp_csv', l: 'ERP - CSV' },
  { v: 'erp_api', l: 'ERP - API' },
  { v: 'manuale', l: 'Manuale' },
]

export default function PMSIntegrationPage() {
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({
    name: '',
    system_type: 'pms_api',
    api_endpoint: '',
    api_key: '',
    username: '',
    password: '',
    sync_frequency_hours: 24,
    config_data: null,
  })
  const qc = useQueryClient()

  const { data: integrations, isLoading } = useQuery({
    queryKey: ['pms-integrations'],
    queryFn: () => pmsIntegrationsApi.list().then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: () => pmsIntegrationsApi.create(form),
    onSuccess: () => {
      toast.success('Integrazione creata')
      setShowForm(false)
      resetForm()
      qc.invalidateQueries({ queryKey: ['pms-integrations'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore creazione'),
  })

  const updateMutation = useMutation({
    mutationFn: (id) => pmsIntegrationsApi.update(id, form),
    onSuccess: () => {
      toast.success('Integrazione aggiornata')
      setShowForm(false)
      setEditingId(null)
      resetForm()
      qc.invalidateQueries({ queryKey: ['pms-integrations'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore aggiornamento'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => pmsIntegrationsApi.delete(id),
    onSuccess: () => {
      toast.success('Integrazione disattivata')
      qc.invalidateQueries({ queryKey: ['pms-integrations'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore eliminazione'),
  })

  const syncMutation = useMutation({
    mutationFn: (id) => pmsIntegrationsApi.sync(id),
    onSuccess: (res) => {
      toast.success('Sync avviato: ' + res.data.message)
      qc.invalidateQueries({ queryKey: ['pms-integrations'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore sync'),
  })

  function openCreate() {
    resetForm()
    setEditingId(null)
    setShowForm(true)
  }

  function openEdit(int) {
    setForm({
      name: int.name,
      system_type: int.system_type,
      api_endpoint: int.api_endpoint || '',
      api_key: int.api_key || '',
      username: int.username || '',
      password: int.password || '',
      sync_frequency_hours: int.sync_frequency_hours || 24,
      config_data: int.config_data || null,
    })
    setEditingId(int.id)
    setShowForm(true)
  }

  function resetForm() {
    setForm({
      name: '',
      system_type: 'pms_api',
      api_endpoint: '',
      api_key: '',
      username: '',
      password: '',
      sync_frequency_hours: 24,
      config_data: null,
    })
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (editingId) {
      updateMutation.mutate(editingId)
    } else {
      createMutation.mutate()
    }
  }

  const activeCount = integrations?.filter(i => i.is_active).length || 0

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Integrazioni PMS / ERP</h1>
          <p style={{ color: 'var(--text-muted)' }}>{integrations?.length || 0} configurazioni ({activeCount} attive)</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '✕ Chiudi' : '+ Nuova Integrazione'}
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
            {editingId ? '✏️ Modifica Integrazione' : '➕ Nuova Integrazione'}
          </div>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
              <div className="form-group">
                <label>Nome *</label>
                <input required value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Mews Cloud" />
              </div>
              <div className="form-group">
                <label>Tipo Sistema *</label>
                <select value={form.system_type} onChange={e => setForm({...form, system_type: e.target.value})}>
                  {SYSTEM_TYPES.map(t => <option key={t.v} value={t.v}>{t.l}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Frequenza Sync (ore)</label>
                <input type="number" min={1} max={168} value={form.sync_frequency_hours} onChange={e => setForm({...form, sync_frequency_hours: parseInt(e.target.value)})} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              <div className="form-group">
                <label>API Endpoint</label>
                <input value={form.api_endpoint} onChange={e => setForm({...form, api_endpoint: e.target.value})} placeholder="https://api.example.com/connector" />
              </div>
              <div className="form-group">
                <label>API Key / Username</label>
                <input value={form.api_key} onChange={e => setForm({...form, api_key: e.target.value})} placeholder="Chiave API" type="password" />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>
                {editingId ? 'Aggiorna' : 'Crea'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); setEditingId(null); resetForm(); }}>
                Annulla
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Lista */}
      {isLoading ? (
        <div>Caricamento...</div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Tipo</th>
                <th>Endpoint</th>
                <th>Frequenza</th>
                <th>Ultimo Sync</th>
                <th>Stato</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {integrations?.map(int => (
                <tr key={int.id}>
                  <td><strong>{int.name}</strong></td>
                  <td>
                    <span className="badge" style={{ background: int.system_type.includes('csv') ? '#e3f2fd' : '#fce4ec' }}>
                      {SYSTEM_TYPES.find(t => t.v === int.system_type)?.l || int.system_type}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={int.api_endpoint || ''}>
                    {int.api_endpoint || '-'}
                  </td>
                  <td>{int.sync_frequency_hours}h</td>
                  <td>{int.last_sync_at ? new Date(int.last_sync_at).toLocaleString('it-IT') : '-'}</td>
                  <td>
                    <span className={`badge ${int.is_active ? 'badge-success' : 'badge-secondary'}`}>
                      {int.is_active ? 'Attiva' : 'Disattivata'}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-sm btn-secondary" onClick={() => openEdit(int)}>Modifica</button>
                      <button className="btn btn-sm btn-primary" onClick={() => syncMutation.mutate(int.id)} disabled={!int.is_active}>
                        Sync
                      </button>
                      <button className="btn btn-sm btn-danger" onClick={() => { if (confirm('Disattivare questa integrazione?')) deleteMutation.mutate(int.id) }}>
                        Elimina
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {(!integrations || integrations.length === 0) && (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
                  Nessuna integrazione configurata. Clicca "+ Nuova Integrazione" per iniziare.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { periodsApi } from '../lib/api'
import { useState } from 'react'
import toast from 'react-hot-toast'

const MONTHS = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']

export default function PeriodsPage() {
  const [year, setYear] = useState(new Date().getFullYear())
  const [month, setMonth] = useState(new Date().getMonth() + 1)
  const qc = useQueryClient()

  const { data: periods, isLoading } = useQuery({
    queryKey: ['periods'],
    queryFn: () => periodsApi.list().then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: () => periodsApi.create({ year, month, name: `${MONTHS[month-1]} ${year}` }),
    onSuccess: () => { toast.success('Periodo creato'); qc.invalidateQueries({ queryKey: ['periods'] }) },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore'),
  })

  return (
    <div className="fade-in">
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 24 }}>Periodi Contabili</h1>
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>➕ Crea Periodo</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <div className="form-group">
            <label>Anno</label>
            <input type="number" value={year} onChange={e => setYear(Number(e.target.value))} style={{ width: 100 }} />
          </div>
          <div className="form-group">
            <label>Mese</label>
            <select value={month} onChange={e => setMonth(Number(e.target.value))} style={{ width: 160 }}>
              {MONTHS.map((m, i) => <option key={i} value={i+1}>{m}</option>)}
            </select>
          </div>
          <button className="btn btn-primary" onClick={() => createMutation.mutate()}>Crea Periodo</button>
        </div>
      </div>
      <div className="table-card">
        <div className="table-header"><div className="table-title">Periodi Configurati</div></div>
        {isLoading ? <div className="loading-center"><div className="spinner" /></div> : (
          <table>
            <thead><tr><th>Periodo</th><th>Anno</th><th>Mese</th><th>Stato</th></tr></thead>
            <tbody>
              {periods?.map(p => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600 }}>{p.name}</td>
                  <td>{p.year}</td>
                  <td>{p.month}</td>
                  <td>{p.is_closed ? <span className="badge badge-neutral">Chiuso</span> : <span className="badge badge-success">Aperto</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

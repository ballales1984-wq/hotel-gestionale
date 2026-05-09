import { useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery } from '@tanstack/react-query'
import { importsApi, periodsApi } from '../lib/api'
import toast from 'react-hot-toast'

function DropZone({ onDrop, accept, label, icon }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: files => onDrop(files[0]),
    accept,
    multiple: false,
  })

  return (
    <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'active' : ''}`}>
      <input {...getInputProps()} />
      <div className="upload-zone-icon">{icon}</div>
      <div className="upload-zone-text">{label}</div>
      <div className="upload-zone-sub">Trascina qui o clicca · CSV, XLSX, XLS</div>
    </div>
  )
}

function ImportCard({ title, desc, icon, importType, periodId }) {
  const [result, setResult] = useState(null)

  const mutation = useMutation({
    mutationFn: (file) => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('period_id', periodId)
      return importsApi[importType](fd)
    },
    onSuccess: (res) => {
      setResult(res.data)
      toast.success(`Import completato: ${res.data.rows_imported} righe importate`)
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Errore durante l\'import'),
  })

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 28 }}>{icon}</span>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{title}</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{desc}</div>
        </div>
      </div>

      {!periodId ? (
        <div className="alert alert-warning">⚠️ Seleziona prima un periodo</div>
      ) : (
        <>
          <DropZone
            onDrop={file => mutation.mutate(file)}
            accept={{ 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] }}
            label={mutation.isPending ? 'Importazione in corso...' : 'Carica file'}
            icon={mutation.isPending ? '⏳' : '📄'}
          />

          {result && (
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
                {[
                  { l: 'Lette', v: result.rows_read, c: '#94a3b8' },
                  { l: 'Importate', v: result.rows_imported, c: '#10b981' },
                  { l: 'Saltate', v: result.rows_skipped, c: '#f59e0b' },
                ].map(item => (
                  <div key={item.l} style={{
                    textAlign: 'center', padding: '12px',
                    background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)',
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: item.c }}>{item.v}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.l}</div>
                  </div>
                ))}
              </div>

              {result.errors?.length > 0 && (
                <div style={{ background: 'rgba(239,68,68,0.08)', borderRadius: 'var(--radius-sm)', padding: 12, maxHeight: 120, overflowY: 'auto' }}>
                  {result.errors.map((e, i) => (
                    <div key={i} style={{ fontSize: 12, color: '#f87171', marginBottom: 4 }}>❌ {e}</div>
                  ))}
                </div>
              )}
              {result.warnings?.length > 0 && (
                <div style={{ background: 'rgba(245,158,11,0.08)', borderRadius: 'var(--radius-sm)', padding: 12, maxHeight: 80, overflowY: 'auto', marginTop: 8 }}>
                  {result.warnings.map((w, i) => (
                    <div key={i} style={{ fontSize: 12, color: '#fbbf24', marginBottom: 4 }}>⚠️ {w}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function ImportPage() {
  const [selectedPeriod, setSelectedPeriod] = useState('')

  const { data: periods } = useQuery({
    queryKey: ['periods'],
    queryFn: () => periodsApi.list().then(r => r.data),
  })

  const IMPORT_TYPES = [
    {
      title: 'Contabilità / Costi',
      desc: 'Importa voci di costo dal gestionale contabile (CSV/Excel)',
      icon: '📊',
      type: 'accounting',
    },
    {
      title: 'Payroll / Ore Personale',
      desc: 'Importa ore lavorate per dipendente e attività',
      icon: '👥',
      type: 'payroll',
    },
    {
      title: 'Ricavi per Servizio',
      desc: 'Importa ricavi da PMS o inserimento manuale',
      icon: '💰',
      type: 'revenues',
    },
  ]

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Import Dati</h1>
        <p style={{ color: 'var(--text-muted)' }}>
          Carica i dati contabili, del personale e i ricavi per eseguire il calcolo ABC
        </p>
      </div>

      {/* Selezione periodo */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="form-group">
          <label>📅 Periodo di riferimento per l'import</label>
          <select value={selectedPeriod} onChange={e => setSelectedPeriod(e.target.value)} style={{ maxWidth: 340 }}>
            <option value="">— Seleziona un periodo —</option>
            {periods?.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Formati attesi */}
      <div className="alert alert-info" style={{ marginBottom: 24 }}>
        ℹ️ <strong>Formato file atteso:</strong> Il sistema rileva automaticamente le colonne. Assicurati che il file
        contenga intestazioni chiare in italiano o inglese. Le colonne chiave per la contabilità sono:
        <code style={{ background: 'rgba(255,255,255,0.1)', padding: '1px 6px', borderRadius: 4, margin: '0 4px' }}>
          conto, descrizione, centro_di_costo, tipo_costo, importo
        </code>
      </div>

      {/* Import cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        {IMPORT_TYPES.map(t => (
          <ImportCard
            key={t.type}
            title={t.title}
            desc={t.desc}
            icon={t.icon}
            importType={t.type}
            periodId={selectedPeriod}
          />
        ))}
      </div>
    </div>
  )
}

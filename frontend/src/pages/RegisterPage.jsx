import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../lib/api'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

const ROLES = [
  { v: 'viewer', l: 'Visualizzatore' },
  { v: 'analyst', l: 'Analista' },
  { v: 'manager', l: 'Responsabile' },
  { v: 'admin', l: 'Amministratore' },
]

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('viewer')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore(s => s.login)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email || !fullName || !password) {
      toast.error('Compila tutti i campi obbligatori')
      return
    }
    setLoading(true)
    try {
      const res = await authApi.register({ email, full_name: fullName, password, role })
      login(res.data.access_token, {
        id: res.data.user_id,
        full_name: res.data.full_name,
        role: res.data.role,
        hotel_id: res.data.hotel_id,
      })
      navigate('/')
      toast.success('Registrazione completata')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Errore registrazione')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-base)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
    }}>
      <div style={{ width: '100%', maxWidth: 420 }}>
        {/* Logo */}
        <div style={{
          width: 64, height: 64,
          background: 'var(--gradient-primary)',
          borderRadius: 'var(--radius-md)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 32, margin: '0 auto 24px',
        }}>
          🏨
        </div>

        <div className="card" style={{ padding: 32 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, textAlign: 'center' }}>
            Crea account
          </h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: 24, textAlign: 'center' }}>
            Registrati per accedere alla piattaforma
          </p>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Nome completo</label>
              <input
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Mario Rossi"
              />
            </div>

            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="mario@esempio.it"
              />
            </div>

            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            <div className="form-group">
              <label>Ruolo</label>
              <select value={role} onChange={e => setRole(e.target.value)}>
                {ROLES.map(r => <option key={r.v} value={r.v}>{r.l}</option>)}
              </select>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: 8 }}
              disabled={loading}
            >
              {loading ? 'Registrazione...' : 'Registrati'}
            </button>
          </form>

          <div style={{ marginTop: 16, textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
            Hai già un account? <a href="/login" style={{ color: 'var(--color-primary)' }}>Accedi</a>
          </div>
        </div>

        <div style={{ textAlign: 'center', marginTop: 24, fontSize: 12, color: 'var(--text-muted)' }}>
          © 2025 Hotel ABC Platform
        </div>
      </div>
    </div>
  )
}

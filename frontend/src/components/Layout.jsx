import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

const NAV_ITEMS = [
  { section: 'Overview', items: [
    { to: '/', icon: '📊', label: 'Dashboard' },
    { to: '/report', icon: '🧮', label: 'Calcolo ABC' },
    { to: '/simulation', icon: '🎯', label: 'Simulazioni What-If' },
    { to: '/ai-insights', icon: '✨', label: 'AI Insights' },
  ]},
  { section: 'Configurazione', items: [
    { to: '/periods', icon: '📅', label: 'Periodi' },
    { to: '/activities', icon: '⚙️', label: 'Attività' },
    { to: '/services', icon: '🏨', label: 'Servizi' },
    { to: '/allocations', icon: '🔀', label: 'Regole di Allocazione' },
    { to: '/pms-integrations', icon: '🔗', label: 'Integrazioni PMS/ERP' },
  ]},
  { section: 'Dati', items: [
    { to: '/import', icon: '📥', label: 'Import Dati' },
  ]},
]

export default function Layout() {
  const user = useAuthStore(s => s.user)
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🏨</div>
          <div>
            <div className="sidebar-logo-text">Hotel ABC</div>
            <div className="sidebar-logo-sub">Controllo di Gestione</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(section => (
            <div key={section.section}>
              <div className="nav-section-label">{section.section}</div>
              {section.items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                >
                  <span className="nav-item-icon">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* User footer */}
        <div style={{ padding: '16px 12px', borderTop: '1px solid var(--bg-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'var(--gradient-primary)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, fontWeight: 700, color: 'white',
            }}>
              {user?.full_name?.[0] || '?'}
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                {user?.full_name || 'Utente'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {user?.role || ''}
              </div>
            </div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={handleLogout} style={{ width: '100%' }}>
            🚪 Esci
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <div className="page-content fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

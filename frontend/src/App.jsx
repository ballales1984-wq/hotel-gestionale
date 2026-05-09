import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ActivitiesPage from './pages/ActivitiesPage'
import ServicesPage from './pages/ServicesPage'
import ImportPage from './pages/ImportPage'
import ABCReportPage from './pages/ABCReportPage'
import SimulationPage from './pages/SimulationPage'
import AllocationsPage from './pages/AllocationsPage'
import PeriodsPage from './pages/PeriodsPage'
import AiInsightsPage from './pages/AiInsightsPage'

function ProtectedRoute({ children }) {
  const token = useAuthStore(s => s.token)
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const token = useAuthStore(s => s.token)

  return (
    <Routes>
      <Route path="/login" element={token ? <Navigate to="/" /> : <LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="activities" element={<ActivitiesPage />} />
        <Route path="services" element={<ServicesPage />} />
        <Route path="allocations" element={<AllocationsPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="periods" element={<PeriodsPage />} />
        <Route path="report" element={<ABCReportPage />} />
        <Route path="simulation" element={<SimulationPage />} />
        <Route path="ai-insights" element={<AiInsightsPage />} />
      </Route>
    </Routes>
  )
}

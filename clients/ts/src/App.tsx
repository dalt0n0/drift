import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Shell } from './components/Shell'
import Login from './screens/Login'
import Dashboard from './screens/Dashboard'
import Findings from './screens/Findings'
import Targets from './screens/Targets'
import Runs from './screens/Runs'
import Vault from './screens/Vault'
import Audit from './screens/Audit'
import Report from './screens/Report'
import Settings from './screens/Settings'
import { getEngagements, getMe } from './api'
import type { Engagement } from './types'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('drift.token')
  const location = useLocation()
  if (!token) return <Navigate to="/login" state={{ from: location }} replace />
  return <>{children}</>
}

type Screen = 'dashboard' | 'targets' | 'findings' | 'runs' | 'report' | 'vault' | 'audit' | 'settings'

function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const qc = useQueryClient()

  const [engagementId, setEngagementId] = useState<string | null>(
    () => localStorage.getItem('drift.engagementId')
  )
  const [railOpen, setRailOpen] = useState(false)

  const { data: user } = useQuery({ queryKey: ['me'], queryFn: getMe, staleTime: 60_000 })
  const { data: engagements = [] } = useQuery({
    queryKey: ['engagements'],
    queryFn: getEngagements,
    staleTime: 30_000,
  })

  const engagement: Engagement | null =
    engagements.find(e => e.id === engagementId) ?? engagements[0] ?? null

  useEffect(() => {
    if (engagement && engagement.id !== engagementId) {
      setEngagementId(engagement.id)
    }
    if (engagement) localStorage.setItem('drift.engagementId', engagement.id)
  }, [engagement, engagementId])

  const screenFromPath = (): Screen => {
    const p = location.pathname
    if (p.startsWith('/findings')) return 'findings'
    if (p.startsWith('/targets')) return 'targets'
    if (p.startsWith('/runs')) return 'runs'
    if (p.startsWith('/report')) return 'report'
    if (p.startsWith('/vault')) return 'vault'
    if (p.startsWith('/audit')) return 'audit'
    if (p.startsWith('/settings')) return 'settings'
    return 'dashboard'
  }

  const handleNav = (screen: Screen) => {
    navigate(`/${screen === 'dashboard' ? '' : screen}`)
  }

  const handleSignOut = () => {
    localStorage.removeItem('drift.token')
    localStorage.removeItem('drift.user')
    localStorage.removeItem('drift.engagementId')
    qc.clear()
    navigate('/login')
  }

  return (
    <Shell
      user={user ?? null}
      engagements={engagements}
      selectedEngagement={engagement}
      onSelectEngagement={e => { setEngagementId(e.id); localStorage.setItem('drift.engagementId', e.id) }}
      screen={screenFromPath()}
      onNav={handleNav}
      railOpen={railOpen}
      onToggleRail={() => setRailOpen(r => !r)}
      onSignOut={handleSignOut}
    >
      <Routes>
        <Route path="/" element={<Dashboard engagement={engagement} onNav={handleNav} />} />
        <Route path="/findings" element={<Findings engagement={engagement} />} />
        <Route path="/targets" element={<Targets engagement={engagement} />} />
        <Route path="/runs" element={<Runs engagement={engagement} />} />
        <Route path="/report" element={<Report engagement={engagement} />} />
        <Route path="/vault" element={<Vault engagement={engagement} />} />
        <Route path="/audit" element={<Audit engagement={engagement} />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={
        <RequireAuth>
          <AppShell />
        </RequireAuth>
      } />
    </Routes>
  )
}

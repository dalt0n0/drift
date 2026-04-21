import { useState } from 'react'
import { Ic } from '../components/Icon'
import { Button, Input } from '../components/primitives'
import { login, getMe } from '../api'
import type { User } from '../types'

interface Props {
  onLogin: (token: string, user: User) => void
}

export default function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!username || !password) { setError('Username and password required.'); return }
    setLoading(true); setError('')
    try {
      const { access_token } = await login(username, password)
      localStorage.setItem('drift.token', access_token)
      const user = await getMe()
      onLogin(access_token, user)
    } catch {
      setError('Invalid credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      {/* Background grid */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 0,
        backgroundImage: 'linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
        maskImage: 'radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%)',
      }} />

      <div style={{ position: 'relative', zIndex: 1, width: 380 }}>
        {/* Logo */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 32 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 10,
            background: 'linear-gradient(135deg, var(--accent), #ff7a00)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 32px rgba(255,170,0,0.25), inset 0 0 0 1px rgba(0,0,0,0.2)',
            marginBottom: 14,
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M12 2 L20 6 V12 C20 17 16 21 12 22 C8 21 4 17 4 12 V6 Z" stroke="#1a1300" strokeWidth="2" strokeLinejoin="round" />
              <path d="M9 12 L11 14 L15 10" stroke="#1a1300" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.03em' }}>Drift</div>
          <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 4 }}>Self-hosted pentest suite</div>
        </div>

        {/* Form card */}
        <div style={{
          background: 'var(--bg-1)', border: '1px solid var(--line-2)',
          borderRadius: 12, padding: 28,
          boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
        }}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 20 }}>Sign in to your workspace</div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>Username</label>
              <Input
                value={username}
                onChange={setUsername}
                placeholder="admin"
                autoFocus
                onKeyDown={e => e.key === 'Enter' && submit()}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>Password</label>
              <div style={{ position: 'relative' }}>
                <Input
                  value={password}
                  onChange={setPassword}
                  type={showPwd ? 'text' : 'password'}
                  placeholder="••••••••"
                  onKeyDown={e => e.key === 'Enter' && submit()}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    color: 'var(--text-3)',
                  }}
                >
                  <Ic name={showPwd ? 'eyeOff' : 'eye'} size={14} />
                </button>
              </div>
            </div>

            {error && (
              <div style={{
                padding: '8px 12px', borderRadius: 6,
                background: 'rgba(255,74,94,0.10)', border: '1px solid rgba(255,74,94,0.25)',
                color: 'var(--crit)', fontSize: 12.5,
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <Ic name="alertTriangle" size={13} />{error}
              </div>
            )}

            <Button
              variant="primary"
              size="lg"
              onClick={submit}
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </div>
        </div>

        <div style={{ textAlign: 'center', marginTop: 20, fontSize: 12, color: 'var(--text-4)' }}>
          Drift v0.1.0 · <span style={{ fontFamily: 'var(--mono)' }}>self-hosted</span>
        </div>
      </div>
    </div>
  )
}

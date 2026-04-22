import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Ic } from '../components/Icon'
import { Button, Input } from '../components/primitives'
import { changePassword } from '../api'

export default function ChangePassword() {
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!current || !next || !confirm) { setError('All fields are required.'); return }
    if (next.length < 12) { setError('New password must be at least 12 characters.'); return }
    if (next !== confirm) { setError('Passwords do not match.'); return }
    setLoading(true); setError('')
    try {
      await changePassword(current, next)
      navigate('/', { replace: true })
    } catch (e: any) {
      setError(e?.response?.data?.detail?.detail || 'Failed to change password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{
        position: 'fixed', inset: 0, zIndex: 0,
        backgroundImage: 'linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
        maskImage: 'radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%)',
      }} />

      <div style={{ position: 'relative', zIndex: 1, width: 400 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 28 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 10,
            background: 'linear-gradient(135deg, var(--accent), #ff7a00)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 32px rgba(255,170,0,0.25), inset 0 0 0 1px rgba(0,0,0,0.2)',
            marginBottom: 14,
          }}>
            <Ic name="lock" size={20} style={{ color: '#1a1300' }} />
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.03em' }}>Change your password</div>
          <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 6, textAlign: 'center', maxWidth: 300 }}>
            Your account requires a password change before you can continue.
          </div>
        </div>

        <div style={{
          background: 'var(--bg-1)', border: '1px solid var(--line-2)',
          borderRadius: 12, padding: 28,
          boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>Current password</label>
              <Input value={current} onChange={setCurrent} type="password" placeholder="••••••••" autoFocus />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>New password</label>
              <Input value={next} onChange={setNext} type="password" placeholder="Min 12 characters" />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>Confirm new password</label>
              <Input value={confirm} onChange={setConfirm} type="password" placeholder="••••••••"
                onKeyDown={(e: React.KeyboardEvent) => e.key === 'Enter' && submit()} />
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

            <div style={{ padding: '8px 12px', borderRadius: 6, background: 'var(--bg-2)', border: '1px solid var(--line)', fontSize: 12, color: 'var(--text-3)' }}>
              Password must be at least 12 characters. All active sessions will be revoked.
            </div>

            <Button variant="primary" size="lg" onClick={submit} disabled={loading}
              style={{ width: '100%', justifyContent: 'center' }}>
              {loading ? 'Updating…' : 'Set new password'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

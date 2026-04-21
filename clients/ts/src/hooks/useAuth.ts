import { useState, useEffect } from 'react'
import type { User } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const raw = localStorage.getItem('drift.user')
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })

  const token = localStorage.getItem('drift.token')
  const isAuthenticated = !!token && !!user

  const signIn = (token: string, user: User) => {
    localStorage.setItem('drift.token', token)
    localStorage.setItem('drift.user', JSON.stringify(user))
    setUser(user)
  }

  const signOut = () => {
    localStorage.removeItem('drift.token')
    localStorage.removeItem('drift.user')
    setUser(null)
  }

  return { user, isAuthenticated, signIn, signOut }
}

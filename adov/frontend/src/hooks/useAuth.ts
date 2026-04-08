// Auth state hook: wraps onAuthStateChanged and keeps a fresh ID token in state.
import { useEffect, useState } from 'react'
import { onAuthStateChanged, User } from 'firebase/auth'
import { auth } from '../lib/firebase'

export interface AuthState {
  user: User | null
  loading: boolean
  idToken: string | null
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [idToken, setIdToken] = useState<string | null>(null)

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser)
      if (firebaseUser) {
        const token = await firebaseUser.getIdToken()
        setIdToken(token)
      } else {
        setIdToken(null)
      }
      setLoading(false)
    })
    return unsubscribe
  }, [])

  // Firebase ID tokens expire after 1 hour. Refresh every 55 minutes so API
  // calls always carry a valid token even after long idle sessions.
  useEffect(() => {
    const interval = setInterval(async () => {
      const currentUser = auth.currentUser
      if (currentUser) {
        try {
          const token = await currentUser.getIdToken(/* forceRefresh */ true)
          setIdToken(token)
        } catch (err) {
          console.error('[useAuth] token refresh failed:', err)
        }
      }
    }, 55 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  return { user, loading, idToken }
}

// Join trip page: shown at /join/:tripId. Prompts sign-in if unauthenticated,
// then adds the user to the trip's memberIds and navigates to the chat.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth'
import { auth, googleProvider } from '../lib/firebase'
import { useAuth } from '../hooks/useAuth'
import { getInviteInfo, joinTrip, updateCalendarToken } from '../api/client'

export default function JoinTripPage() {
  const { tripId } = useParams<{ tripId: string }>()
  const { user, loading, idToken } = useAuth()
  const navigate = useNavigate()
  const [tripInfo, setTripInfo] = useState<{ member_count: number; exists: boolean } | null>(null)
  const [joining, setJoining] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!tripId) return
    getInviteInfo(tripId)
      .then(setTripInfo)
      .catch(() => setTripInfo({ member_count: 0, exists: false }))
  }, [tripId])

  const handleJoin = async () => {
    if (!tripId || !idToken) return
    setJoining(true)
    setError(null)
    try {
      await joinTrip(tripId, idToken)
      navigate(`/trips/${tripId}`)
    } catch (err) {
      setError('Failed to join trip. Try again.')
      setJoining(false)
    }
  }

  const handleSignIn = async () => {
    setError(null)
    try {
      const result = await signInWithPopup(auth, googleProvider)
      const credential = GoogleAuthProvider.credentialFromResult(result)
      const token = await result.user.getIdToken()
      if (credential?.accessToken) {
        try { await updateCalendarToken(credential.accessToken, token) } catch { /* ignore */ }
      }
      // After sign-in, the useAuth hook will update and re-render — join happens via button
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Sign-in failed')
    }
  }

  if (!tripId) return null

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100dvh',
        background: '#F2F2F7',
        padding: '24px',
      }}
    >
      <div
        style={{
          width: '72px',
          height: '72px',
          borderRadius: '18px',
          background: 'linear-gradient(135deg,#5856D6,#007AFF)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '34px',
          marginBottom: '20px',
          boxShadow: '0 4px 16px rgba(88,86,214,0.3)',
        }}
      >
        ✈️
      </div>

      <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#000', margin: '0 0 6px' }}>
        You're invited!
      </h1>
      <p style={{ fontSize: '14px', color: '#8E8E93', margin: '0 0 4px' }}>
        Trip: <strong style={{ color: '#000' }}>{tripId}</strong>
      </p>
      {tripInfo && (
        <p style={{ fontSize: '13px', color: '#8E8E93', margin: '0 0 40px' }}>
          {tripInfo.member_count} {tripInfo.member_count === 1 ? 'member' : 'members'} planning
        </p>
      )}

      {loading ? (
        <p style={{ color: '#8E8E93', fontSize: '14px' }}>Loading…</p>
      ) : !user ? (
        <>
          <p style={{ fontSize: '14px', color: '#3C3C43', marginBottom: '20px', textAlign: 'center' }}>
            Sign in with Google to join this trip.
          </p>
          <button
            onClick={handleSignIn}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '14px 24px', borderRadius: '14px', background: '#fff',
              border: '1px solid rgba(0,0,0,0.12)', fontSize: '16px',
              fontWeight: '600', color: '#000', cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)', width: '100%',
              maxWidth: '300px', justifyContent: 'center',
            }}
          >
            Continue with Google
          </button>
        </>
      ) : (
        <>
          <p style={{ fontSize: '14px', color: '#3C3C43', marginBottom: '20px', textAlign: 'center' }}>
            Joining as <strong>{user.displayName}</strong>
          </p>
          <button
            onClick={handleJoin}
            disabled={joining}
            style={{
              padding: '14px 32px', borderRadius: '14px',
              background: 'linear-gradient(135deg,#5856D6,#007AFF)',
              border: 'none', fontSize: '16px', fontWeight: '600',
              color: '#fff', cursor: joining ? 'default' : 'pointer',
              opacity: joining ? 0.7 : 1,
              boxShadow: '0 2px 12px rgba(0,122,255,0.4)',
            }}
          >
            {joining ? 'Joining…' : 'Join Trip'}
          </button>
        </>
      )}

      {error && (
        <p style={{ marginTop: '16px', fontSize: '13px', color: '#FF3B30', textAlign: 'center' }}>
          {error}
        </p>
      )}
    </div>
  )
}

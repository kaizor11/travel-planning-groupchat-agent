// Sign-in page: iOS-style full-screen with "Continue with Google" button.
// After successful sign-in, stores the Google OAuth access token for Calendar
// and navigates to the default trip.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth'
import { auth, googleProvider } from '../lib/firebase'
import { updateCalendarToken } from '../api/client'

export default function LoginPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleGoogleSignIn = async () => {
    setError(null)
    setLoading(true)
    try {
      const result = await signInWithPopup(auth, googleProvider)
      const credential = GoogleAuthProvider.credentialFromResult(result)
      const idToken = await result.user.getIdToken()

      // Store the Google OAuth access token so the backend can query Calendar
      if (credential?.accessToken) {
        try {
          await updateCalendarToken(credential.accessToken, idToken)
        } catch {
          // Non-blocking — calendar token storage failure doesn't block sign-in
          console.warn('[TripMind] Failed to store calendar token')
        }
      }

      navigate('/trips/test-trip-123')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Sign-in failed'
      setError(msg)
      setLoading(false)
    }
  }

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
      {/* Logo */}
      <div
        style={{
          width: '80px',
          height: '80px',
          borderRadius: '20px',
          background: 'linear-gradient(135deg,#5856D6,#007AFF)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '38px',
          marginBottom: '20px',
          boxShadow: '0 4px 20px rgba(88,86,214,0.35)',
        }}
      >
        ✈️
      </div>

      <h1
        style={{
          fontSize: '28px',
          fontWeight: '700',
          color: '#000',
          margin: '0 0 8px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
        }}
      >
        TripMind
      </h1>
      <p
        style={{
          fontSize: '15px',
          color: '#8E8E93',
          margin: '0 0 48px',
          textAlign: 'center',
          maxWidth: '260px',
          lineHeight: '1.5',
        }}
      >
        Plan group trips together — no spreadsheets, no drama.
      </p>

      {/* Sign-in button */}
      <button
        onClick={handleGoogleSignIn}
        disabled={loading}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '14px 24px',
          borderRadius: '14px',
          background: '#fff',
          border: '1px solid rgba(0,0,0,0.12)',
          fontSize: '16px',
          fontWeight: '600',
          color: '#000',
          cursor: loading ? 'default' : 'pointer',
          opacity: loading ? 0.6 : 1,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          width: '100%',
          maxWidth: '300px',
          justifyContent: 'center',
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif',
        }}
      >
        {/* Google G logo */}
        <svg width="20" height="20" viewBox="0 0 48 48" fill="none">
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        </svg>
        {loading ? 'Signing in…' : 'Continue with Google'}
      </button>

      {error && (
        <p
          style={{
            marginTop: '16px',
            fontSize: '13px',
            color: '#FF3B30',
            textAlign: 'center',
            maxWidth: '280px',
          }}
        >
          {error}
        </p>
      )}

      <p
        style={{
          position: 'absolute',
          bottom: '32px',
          fontSize: '12px',
          color: '#C7C7CC',
          textAlign: 'center',
        }}
      >
        Calendar access is read-only — we only see free/busy times.
      </p>
    </div>
  )
}

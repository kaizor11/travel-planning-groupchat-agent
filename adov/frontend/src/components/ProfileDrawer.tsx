// Slide-in profile drawer: lets the user set private budget range and travel preferences.
// Budget data is stored server-side and NEVER shared with other group members.
import { useEffect, useState } from 'react'
import type { User } from 'firebase/auth'
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth'
import { auth } from '../lib/firebase'
import { getProfile, updateProfile, updateCalendarToken } from '../api/client'

const PREFERENCE_TAGS = ['beach', 'hiking', 'city', 'adventure', 'culture', 'food', 'relaxation', 'nightlife', 'nature', 'ski']

interface ProfileDrawerProps {
  user: User | null
  idToken: string
  onClose: () => void
}

export default function ProfileDrawer({ user, idToken, onClose }: ProfileDrawerProps) {
  const [budgetMin, setBudgetMin] = useState('')
  const [budgetMax, setBudgetMax] = useState('')
  const [preferences, setPreferences] = useState<string[]>([])
  const [homeAirport, setHomeAirport] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [calendarConnected, setCalendarConnected] = useState<boolean | null>(null)
  const [calendarConnecting, setCalendarConnecting] = useState(false)
  const [calendarError, setCalendarError] = useState<string | null>(null)
  const [profileLoadError, setProfileLoadError] = useState(false)

  const loadProfile = async (token: string) => {
    setProfileLoadError(false)
    setCalendarConnected(null)
    try {
      const profile = await getProfile(token)
      if (profile.budgetMin != null) setBudgetMin(String(profile.budgetMin))
      if (profile.budgetMax != null) setBudgetMax(String(profile.budgetMax))
      if (profile.preferences) setPreferences(profile.preferences)
      if (profile.homeAirport) setHomeAirport(profile.homeAirport)
      setCalendarConnected(profile.calendarConnected ?? false)
    } catch {
      setProfileLoadError(true)
      setCalendarConnected(false)
    }
  }

  // Load existing profile on mount (or when token refreshes)
  useEffect(() => {
    loadProfile(idToken)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idToken])

  const handleRetryProfile = async () => {
    // Force-refresh token before retrying in case the cause was token expiry
    try {
      const { auth: firebaseAuth } = await import('../lib/firebase')
      const freshToken = await firebaseAuth.currentUser?.getIdToken(true)
      if (freshToken) {
        await loadProfile(freshToken)
        return
      }
    } catch { /* fall through to retry with current token */ }
    await loadProfile(idToken)
  }

  const handleConnectCalendar = async () => {
    setCalendarConnecting(true)
    setCalendarError(null)
    try {
      // Create a fresh provider each time with prompt:'consent' so Google always
      // re-issues an access token that includes the calendar.readonly scope.
      // Using the module-level singleton with prompt:'select_account' can skip
      // consent for already-signed-in users, returning a token without calendar scope.
      const calendarProvider = new GoogleAuthProvider()
      calendarProvider.addScope('https://www.googleapis.com/auth/calendar.readonly')
      calendarProvider.setCustomParameters({ prompt: 'consent' })

      const result = await signInWithPopup(auth, calendarProvider)
      const credential = GoogleAuthProvider.credentialFromResult(result)
      if (!credential?.accessToken) {
        setCalendarError('No calendar token returned. Try signing out and back in.')
        return
      }
      // Use the idToken prop (the session token proven valid by existing GET calls)
      // instead of result.user.getIdToken(), which can fail verify_id_token right
      // after signInWithPopup completes its session handshake.
      await updateCalendarToken(credential.accessToken, idToken)
      const profile = await getProfile(idToken)
      setCalendarConnected(profile.calendarConnected ?? false)
    } catch {
      setCalendarError('Failed to connect calendar. Try again.')
    } finally {
      setCalendarConnecting(false)
    }
  }

  const togglePreference = (tag: string) => {
    setPreferences(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    )
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateProfile({
        budgetMin: budgetMin ? parseInt(budgetMin, 10) : undefined,
        budgetMax: budgetMax ? parseInt(budgetMax, 10) : undefined,
        preferences,
        homeAirport: homeAirport.trim() || undefined,
      }, idToken)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      // ignore — user can retry
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.3)',
          zIndex: 40,
        }}
      />

      {/* Drawer */}
      <div
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: 'min(320px, 90vw)',
          background: '#F2F2F7',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '-4px 0 20px rgba(0,0,0,0.12)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '56px 20px 16px',
            background: '#fff',
            borderBottom: '1px solid rgba(0,0,0,0.08)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {user?.photoURL ? (
              <img
                src={user.photoURL}
                alt="avatar"
                style={{ width: 44, height: 44, borderRadius: '50%' }}
              />
            ) : (
              <div
                style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: 'linear-gradient(135deg,#5856D6,#007AFF)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontWeight: '700', fontSize: '18px',
                }}
              >
                {user?.displayName?.[0]?.toUpperCase() ?? '?'}
              </div>
            )}
            <div>
              <p style={{ fontWeight: '600', fontSize: '16px', color: '#000', margin: 0 }}>
                {user?.displayName ?? 'Your Profile'}
              </p>
              <p style={{ fontSize: '12px', color: '#8E8E93', margin: 0 }}>{user?.email}</p>
            </div>
            <button
              onClick={onClose}
              style={{
                marginLeft: 'auto', background: 'none', border: 'none',
                fontSize: '22px', color: '#8E8E93', cursor: 'pointer', lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 16px' }}>

          {/* Google Calendar section */}
          <div
            style={{
              background: '#fff', borderRadius: '12px',
              padding: '16px', marginBottom: '16px',
            }}
          >
            <p style={{ fontSize: '13px', fontWeight: '600', color: '#000', margin: '0 0 4px' }}>
              Google Calendar
            </p>
            <p style={{ fontSize: '12px', color: '#8E8E93', margin: '0 0 12px' }}>
              Read-only — we only see free/busy times
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '5px',
                  fontSize: '13px',
                  color: calendarConnected === null
                    ? '#8E8E93'
                    : calendarConnected ? '#34C759' : '#FF9500',
                  fontWeight: '500',
                }}
              >
                <span style={{ fontSize: '10px' }}>●</span>
                {calendarConnected === null ? 'Checking…' : calendarConnected ? 'Connected' : 'Not connected'}
              </span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
                {profileLoadError && (
                  <button
                    onClick={handleRetryProfile}
                    style={{
                      padding: '7px 12px', borderRadius: '8px', border: 'none',
                      background: '#F2F2F7', color: '#FF3B30',
                      fontSize: '13px', fontWeight: '600', cursor: 'pointer',
                    }}
                  >
                    Retry
                  </button>
                )}
                <button
                  onClick={handleConnectCalendar}
                  disabled={calendarConnecting}
                  style={{
                    padding: '7px 14px', borderRadius: '8px', border: 'none',
                    background: calendarConnected ? '#F2F2F7' : '#007AFF',
                    color: calendarConnected ? '#3C3C43' : '#fff',
                    fontSize: '13px', fontWeight: '600',
                    cursor: calendarConnecting ? 'default' : 'pointer',
                    opacity: calendarConnecting ? 0.6 : 1,
                  }}
                >
                  {calendarConnecting ? 'Connecting…' : calendarConnected ? 'Reconnect' : 'Connect'}
                </button>
              </div>
            </div>
            {calendarError && (
              <p style={{ fontSize: '12px', color: '#FF3B30', margin: '8px 0 0' }}>
                {calendarError}
              </p>
            )}
            {profileLoadError && !calendarError && (
              <p style={{ fontSize: '12px', color: '#FF9500', margin: '8px 0 0' }}>
                Could not load profile — server may be waking up. Tap Retry.
              </p>
            )}
          </div>

          {/* Budget section */}
          <div
            style={{
              background: '#fff', borderRadius: '12px',
              padding: '16px', marginBottom: '16px',
            }}
          >
            <p style={{ fontSize: '13px', fontWeight: '600', color: '#000', margin: '0 0 4px' }}>
              Budget
            </p>
            <p style={{ fontSize: '12px', color: '#8E8E93', margin: '0 0 12px' }}>
              🔒 Private — only you see this
            </p>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: '11px', color: '#8E8E93', display: 'block', marginBottom: '4px' }}>
                  Min ($)
                </label>
                <input
                  type="number"
                  value={budgetMin}
                  onChange={e => setBudgetMin(e.target.value)}
                  placeholder="500"
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: '8px',
                    border: '1px solid rgba(0,0,0,0.12)', fontSize: '15px',
                    background: '#F2F2F7', outline: 'none', boxSizing: 'border-box',
                  }}
                />
              </div>
              <span style={{ color: '#C7C7CC', marginTop: '16px' }}>—</span>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: '11px', color: '#8E8E93', display: 'block', marginBottom: '4px' }}>
                  Max ($)
                </label>
                <input
                  type="number"
                  value={budgetMax}
                  onChange={e => setBudgetMax(e.target.value)}
                  placeholder="2000"
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: '8px',
                    border: '1px solid rgba(0,0,0,0.12)', fontSize: '15px',
                    background: '#F2F2F7', outline: 'none', boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>
          </div>

          {/* Home airport section */}
          <div
            style={{
              background: '#fff', borderRadius: '12px',
              padding: '16px', marginBottom: '16px',
            }}
          >
            <p style={{ fontSize: '13px', fontWeight: '600', color: '#000', margin: '0 0 4px' }}>
              Home Airport
            </p>
            <p style={{ fontSize: '12px', color: '#8E8E93', margin: '0 0 12px' }}>
              Used for real flight price estimates in trip proposals
            </p>
            <input
              type="text"
              value={homeAirport}
              onChange={e => setHomeAirport(e.target.value.toUpperCase())}
              placeholder="LAX"
              maxLength={10}
              style={{
                width: '100%', padding: '10px 12px', borderRadius: '8px',
                border: '1px solid rgba(0,0,0,0.12)', fontSize: '15px',
                background: '#F2F2F7', outline: 'none', boxSizing: 'border-box',
                textTransform: 'uppercase', letterSpacing: '1px',
              }}
            />
          </div>

          {/* Preferences section */}
          <div
            style={{
              background: '#fff', borderRadius: '12px',
              padding: '16px', marginBottom: '24px',
            }}
          >
            <p style={{ fontSize: '13px', fontWeight: '600', color: '#000', margin: '0 0 12px' }}>
              Travel Style
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {PREFERENCE_TAGS.map(tag => {
                const active = preferences.includes(tag)
                return (
                  <button
                    key={tag}
                    onClick={() => togglePreference(tag)}
                    style={{
                      padding: '6px 14px', borderRadius: '20px', border: 'none',
                      fontSize: '13px', fontWeight: active ? '600' : '400',
                      background: active ? '#007AFF' : '#F2F2F7',
                      color: active ? '#fff' : '#000',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                  >
                    {tag}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Save button */}
        <div style={{ padding: '16px', background: '#fff', borderTop: '1px solid rgba(0,0,0,0.08)' }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              width: '100%', padding: '14px',
              borderRadius: '12px', border: 'none',
              background: saved ? '#34C759' : 'linear-gradient(135deg,#5856D6,#007AFF)',
              color: '#fff', fontSize: '16px', fontWeight: '600',
              cursor: saving ? 'default' : 'pointer',
              opacity: saving ? 0.7 : 1,
              transition: 'background 0.2s',
            }}
          >
            {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </>
  )
}

// Slide-in profile drawer: lets the user set private budget range and travel preferences.
// Budget data is stored server-side and NEVER shared with other group members.
import { useEffect, useState } from 'react'
import type { User } from 'firebase/auth'
import { getProfile, updateProfile } from '../api/client'

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
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Load existing profile on mount
  useEffect(() => {
    getProfile(idToken).then(profile => {
      if (profile.budgetMin != null) setBudgetMin(String(profile.budgetMin))
      if (profile.budgetMax != null) setBudgetMax(String(profile.budgetMax))
      if (profile.preferences) setPreferences(profile.preferences)
    }).catch(() => { /* ignore — first time user */ })
  }, [idToken])

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

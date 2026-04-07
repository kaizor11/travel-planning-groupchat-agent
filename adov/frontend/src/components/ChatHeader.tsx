// Frosted glass iOS-style chat header with profile drawer trigger and invite link copy.
import { useState } from 'react'

interface ChatHeaderProps {
  tripId: string
  onProfileOpen: () => void
}

export default function ChatHeader({ tripId, onProfileOpen }: ChatHeaderProps) {
  const [copied, setCopied] = useState(false)

  const handleCopyInvite = () => {
    const link = `${window.location.origin}/join/${tripId}`
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <header className="im-header">
      <div style={{ height: 'env(safe-area-inset-top, 0px)' }} />
      <div className="flex items-center px-2 py-1.5 gap-1">
        {/* Back / profile button */}
        <button
          className="flex items-center gap-0.5 px-1 py-1 rounded-lg active:opacity-50 min-w-[44px]"
          style={{ color: '#007AFF' }}
          onClick={onProfileOpen}
          title="Your profile"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </button>

        {/* Center */}
        <div className="flex-1 flex flex-col items-center gap-0.5">
          <div className="relative flex items-center justify-center">
            <div
              className="w-[42px] h-[42px] rounded-full flex items-center justify-center text-white text-xl font-semibold shadow-sm"
              style={{ background: 'linear-gradient(135deg,#5856D6,#007AFF)' }}
            >
              ✈️
            </div>
            <span
              className="absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white"
              style={{ background: '#34C759' }}
            />
          </div>
          <div className="flex flex-col items-center leading-tight">
            <span className="font-semibold tracking-tight text-black" style={{ fontSize: '13px' }}>TripMind</span>
            <span style={{ fontSize: '11px', color: '#8E8E93' }}>Group · {tripId}</span>
          </div>
        </div>

        {/* Icons */}
        <div className="flex items-center gap-3 min-w-[44px] justify-end pr-1" style={{ color: '#007AFF' }}>
          {/* Copy invite link */}
          <button
            className="active:opacity-50"
            onClick={handleCopyInvite}
            title={copied ? 'Link copied!' : 'Copy invite link'}
          >
            {copied ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#34C759" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            )}
          </button>
          {/* Video call placeholder */}
          <button className="active:opacity-50">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}

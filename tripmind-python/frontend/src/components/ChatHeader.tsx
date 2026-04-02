// Frosted glass iOS-style chat header displaying the trip avatar, name, and action buttons.
interface ChatHeaderProps {
  tripId: string
}

export default function ChatHeader({ tripId }: ChatHeaderProps) {
  return (
    <header className="im-header">
      <div style={{ height: 'env(safe-area-inset-top, 0px)' }} />
      <div className="flex items-center px-2 py-1.5 gap-1">
        {/* Back */}
        <button
          className="flex items-center gap-0.5 px-1 py-1 rounded-lg active:opacity-50 min-w-[44px]"
          style={{ color: '#007AFF' }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
          <span style={{ fontSize: '16px' }}>Back</span>
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
          <button className="active:opacity-50">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </button>
          <button className="active:opacity-50">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.81a19.79 19.79 0 01-3.07-8.67A2 2 0 012 .18h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 14.92z" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}

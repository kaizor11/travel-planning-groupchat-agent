// Renders a single chat message as a sent (blue), received (gray), or AI (purple) bubble.
// Received messages show the sender's name above the bubble for multi-user attribution.
// Timestamps are displayed below each bubble as relative time (e.g. "2m ago").
import ReactMarkdown from 'react-markdown'
import type { Message } from '../types/message'
import WishPoolCard from './WishPoolCard'
import ProposalCard from './ProposalCard'

interface MessageBubbleProps {
  message: Message
  currentUserId: string
  tripId: string
  idToken: string
}

function getInitials(name: string | undefined, senderId: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(' ')
    return parts.length > 1
      ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
      : parts[0][0].toUpperCase()
  }
  return senderId[0]?.toUpperCase() ?? '?'
}

/** Format an ISO timestamp as a human-readable relative time (no external dependencies). */
function formatRelativeTime(ts: string | undefined): string | null {
  if (!ts) return null
  const date = new Date(ts)
  if (isNaN(date.getTime())) return null
  const diffMs = Date.now() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  if (diffSecs < 60) return 'just now'
  const diffMins = Math.floor(diffSecs / 60)
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  // Older than a week — show date
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

const timestampStyle: React.CSSProperties = {
  fontSize: '10px',
  color: '#AEAEB2',
  marginTop: '2px',
  paddingLeft: '4px',
}

export default function MessageBubble({ message, currentUserId, tripId, idToken }: MessageBubbleProps) {
  const isSent = message.senderId === currentUserId
  const isAi = message.senderId === 'ai'
  const initials = getInitials(message.senderName, message.senderId)
  const displayName = message.senderName || message.senderId
  const relativeTime = formatRelativeTime(message.timestamp)

  if (message.type === 'proposal' && message.proposalsData && message.proposalsData.length > 0) {
    return (
      <div className="flex items-end gap-2 px-3 mb-1 im-bubble-wrap">
        <div className="im-avatar im-avatar-ai flex-shrink-0" style={{ fontSize: '13px' }}>✈️</div>
        <div className="flex flex-col gap-2" style={{ maxWidth: '320px' }}>
          <div className="relative">
            <div className="im-bubble im-bubble-ai"><ReactMarkdown>{message.text}</ReactMarkdown></div>
            <div className="im-bubble-ai-clear" />
          </div>
          {message.proposalsData.map(proposal => (
            <ProposalCard
              key={proposal.proposalId}
              proposal={proposal}
              tripId={tripId}
              idToken={idToken}
              currentUserId={currentUserId}
            />
          ))}
          {relativeTime && <span style={{ ...timestampStyle, paddingLeft: '0' }}>{relativeTime}</span>}
        </div>
      </div>
    )
  }

  if (message.type === 'wishpool_confirm' && message.parsedData) {
    return (
      <div className="flex items-end gap-2 px-3 mb-1 im-bubble-wrap">
        <div className="im-avatar im-avatar-ai flex-shrink-0" style={{ fontSize: '13px' }}>✈️</div>
        <div className="flex flex-col gap-1.5">
          <div className="relative">
            <div className="im-bubble im-bubble-ai"><ReactMarkdown>{message.text}</ReactMarkdown></div>
            <div className="im-bubble-ai-clear" />
          </div>
          <WishPoolCard message={message} tripId={tripId} idToken={idToken} />
          {relativeTime && <span style={{ ...timestampStyle, paddingLeft: '0' }}>{relativeTime}</span>}
        </div>
      </div>
    )
  }

  if (isSent) {
    return (
      <div className="flex justify-end px-3 mb-0.5 im-bubble-wrap">
        <div className="flex flex-col items-end">
          <div className="relative">
            <div className="im-bubble im-bubble-sent">{message.text}</div>
            <div className="im-bubble-sent-clear" />
          </div>
          {relativeTime && <span style={{ ...timestampStyle, paddingRight: '4px', paddingLeft: 0 }}>{relativeTime}</span>}
        </div>
      </div>
    )
  }

  if (isAi) {
    return (
      <div className="flex items-end gap-2 px-3 mb-0.5 im-bubble-wrap">
        <div className="im-avatar im-avatar-ai flex-shrink-0" style={{ fontSize: '13px' }}>✈️</div>
        <div className="flex flex-col gap-0.5 max-w-[280px]">
          <div className="relative">
            <div className="im-bubble im-bubble-ai"><ReactMarkdown>{message.text}</ReactMarkdown></div>
            <div className="im-bubble-ai-clear" />
          </div>
          {relativeTime && <span style={timestampStyle}>{relativeTime}</span>}
        </div>
      </div>
    )
  }

  // Received message from another user — show name label above bubble
  return (
    <div className="flex items-end gap-2 px-3 mb-0.5 im-bubble-wrap">
      <div className="im-avatar im-avatar-user flex-shrink-0">{initials}</div>
      <div className="flex flex-col gap-0.5 max-w-[280px]">
        <span
          style={{
            fontSize: '11px',
            color: '#8E8E93',
            paddingLeft: '4px',
            fontWeight: 500,
          }}
        >
          {displayName}
        </span>
        <div className="relative">
          <div className="im-bubble im-bubble-received">{message.text}</div>
          <div className="im-bubble-received-clear" />
        </div>
        {relativeTime && <span style={timestampStyle}>{relativeTime}</span>}
      </div>
    </div>
  )
}

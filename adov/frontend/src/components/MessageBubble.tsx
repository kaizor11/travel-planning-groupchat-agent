// Renders a single chat message as a sent (blue), received (gray), or AI (purple) bubble.
// Received messages show the sender's name above the bubble for multi-user attribution.
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

export default function MessageBubble({ message, currentUserId, tripId, idToken }: MessageBubbleProps) {
  const isSent = message.senderId === currentUserId
  const isAi = message.senderId === 'ai'
  const initials = getInitials(message.senderName, message.senderId)
  const displayName = message.senderName || message.senderId

  if (message.type === 'proposal' && message.proposalsData && message.proposalsData.length > 0) {
    return (
      <div className="flex items-end gap-2 px-3 mb-1 im-bubble-wrap">
        <div className="im-avatar im-avatar-ai flex-shrink-0" style={{ fontSize: '13px' }}>✈️</div>
        <div className="flex flex-col gap-2" style={{ maxWidth: '320px' }}>
          <div className="relative">
            <div className="im-bubble im-bubble-ai">{message.text}</div>
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
            <div className="im-bubble im-bubble-ai">{message.text}</div>
            <div className="im-bubble-ai-clear" />
          </div>
          <WishPoolCard message={message} tripId={tripId} idToken={idToken} />
        </div>
      </div>
    )
  }

  if (isSent) {
    return (
      <div className="flex justify-end px-3 mb-0.5 im-bubble-wrap">
        <div className="relative">
          <div className="im-bubble im-bubble-sent">{message.text}</div>
          <div className="im-bubble-sent-clear" />
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
            <div className="im-bubble im-bubble-ai">{message.text}</div>
            <div className="im-bubble-ai-clear" />
          </div>
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
      </div>
    </div>
  )
}

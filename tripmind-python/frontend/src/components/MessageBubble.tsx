// Renders a single chat message as a sent (blue), received (gray), or AI (purple) bubble with iMessage styling.
import type { Message } from '../types/message'
import WishPoolCard from './WishPoolCard'

interface MessageBubbleProps {
  message: Message
  currentUserId: string
  tripId: string
}

export default function MessageBubble({ message, currentUserId, tripId }: MessageBubbleProps) {
  const isSent = message.senderId === currentUserId
  const isAi = message.senderId === 'ai'
  const initial = message.senderId ? message.senderId[0].toUpperCase() : '?'

  if (message.type === 'wishpool_confirm' && message.parsedData) {
    return (
      <div className="flex items-end gap-2 px-3 mb-1 im-bubble-wrap">
        <div className="im-avatar im-avatar-ai flex-shrink-0" style={{ fontSize: '13px' }}>✈️</div>
        <div className="flex flex-col gap-1.5">
          <div className="relative">
            <div className="im-bubble im-bubble-ai">{message.text}</div>
            <div className="im-bubble-ai-clear" />
          </div>
          <WishPoolCard message={message} tripId={tripId} currentUserId={currentUserId} />
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

  return (
    <div className="flex items-end gap-2 px-3 mb-0.5 im-bubble-wrap">
      <div className="im-avatar im-avatar-user flex-shrink-0">{initial}</div>
      <div className="flex flex-col gap-0.5 max-w-[280px]">
        <div className="relative">
          <div className="im-bubble im-bubble-received">{message.text}</div>
          <div className="im-bubble-received-clear" />
        </div>
      </div>
    </div>
  )
}

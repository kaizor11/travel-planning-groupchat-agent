import { TripMessage } from "@/lib/firestore/trips";
import { WishPoolConfirmCard } from "./WishPoolConfirmCard";

interface MessageBubbleProps {
  message: TripMessage;
  tripId: string;
  currentUserId: string;
  showSender: boolean;
  showTail: boolean;
}

function getSenderInitial(senderId: string): string {
  return senderId.charAt(0).toUpperCase();
}

export function MessageBubble({
  message,
  tripId,
  currentUserId,
  showSender,
  showTail,
}: MessageBubbleProps) {
  const isCurrentUser = message.senderId === currentUserId;
  const isAi = message.senderId === "ai";

  // ── WishPool confirm card (from AI) ──
  if (message.type === "wishpool_confirm" && message.parsedData) {
    return (
      <div className="flex items-end gap-2 px-3 mb-1 im-bubble-wrap">
        {/* AI avatar */}
        <div className="im-avatar im-avatar-ai flex-shrink-0" style={{ width: 26, height: 26, fontSize: 12 }}>
          ✈️
        </div>
        <div className="flex flex-col gap-1.5 max-w-[280px]">
          {showSender && (
            <span className="text-[11px] font-medium px-1" style={{ color: "#8E8E93" }}>
              TripMind
            </span>
          )}
          {/* Preamble text in AI bubble */}
          <div className="relative">
            <div className="im-bubble im-bubble-ai" style={{ maxWidth: 260 }}>
              {message.text}
            </div>
            <div className="im-bubble-ai-clear" />
          </div>
          {/* Rich card below the bubble */}
          <WishPoolConfirmCard
            tripId={tripId}
            senderId={currentUserId}
            parsedData={message.parsedData}
            sourceUrl={message.attachedUrl}
          />
        </div>
      </div>
    );
  }

  // ── Right-aligned: current user ──
  if (isCurrentUser) {
    return (
      <div className="flex justify-end items-end gap-0 px-3 mb-0.5 im-bubble-wrap">
        <div className="relative">
          <div className="im-bubble im-bubble-sent">
            {message.text}
          </div>
          {showTail && <div className="im-bubble-sent-clear" />}
        </div>
      </div>
    );
  }

  // ── Left-aligned: other user or AI ──
  const bubbleClass = isAi ? "im-bubble-ai" : "im-bubble-received";
  const clearClass = isAi ? "im-bubble-ai-clear" : "im-bubble-received-clear";
  const senderLabel = isAi ? "TripMind" : message.senderId;

  return (
    <div className="flex items-end gap-2 px-3 mb-0.5 im-bubble-wrap">
      {/* Avatar */}
      <div
        className={`im-avatar flex-shrink-0 ${isAi ? "im-avatar-ai" : "im-avatar-user"}`}
        style={{
          width: 26,
          height: 26,
          fontSize: 11,
          visibility: showTail ? "visible" : "hidden",
        }}
      >
        {isAi ? "✈️" : getSenderInitial(message.senderId)}
      </div>

      <div className="flex flex-col gap-0.5 max-w-[280px]">
        {showSender && !isAi && (
          <span className="text-[11px] font-medium px-1" style={{ color: "#8E8E93" }}>
            {senderLabel}
          </span>
        )}
        <div className="relative">
          <div className={`im-bubble ${bubbleClass}`}>
            {message.text}
          </div>
          {showTail && <div className={clearClass} />}
        </div>
      </div>
    </div>
  );
}

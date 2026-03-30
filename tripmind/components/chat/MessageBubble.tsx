import { TripMessage } from "@/lib/firestore/trips";
import { WishPoolConfirmCard } from "./WishPoolConfirmCard";

interface MessageBubbleProps {
  message: TripMessage;
  tripId: string;
  currentUserId: string;
}

export function MessageBubble({ message, tripId, currentUserId }: MessageBubbleProps) {
  const isCurrentUser = message.senderId === currentUserId;
  const isAi = message.senderId === "ai";

  if (message.type === "wishpool_confirm" && message.parsedData) {
    return (
      <div className="flex flex-col gap-1 max-w-[75%]">
        <p className="text-xs text-muted-foreground px-1">TripMind</p>
        <p className="text-sm mb-2">{message.text}</p>
        <WishPoolConfirmCard
          tripId={tripId}
          senderId={currentUserId}
          parsedData={message.parsedData}
          sourceUrl={message.attachedUrl}
        />
      </div>
    );
  }

  return (
    <div
      className={`flex ${isCurrentUser ? "justify-end" : "justify-start"}`}
    >
      <div className="flex flex-col gap-1 max-w-[75%]">
        {!isCurrentUser && (
          <p className="text-xs text-muted-foreground px-1">
            {isAi ? "TripMind" : message.senderId}
          </p>
        )}
        <div
          className={`rounded-2xl px-4 py-2 text-sm ${
            isCurrentUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : isAi
              ? "bg-muted text-foreground rounded-tl-sm"
              : "bg-secondary text-secondary-foreground rounded-tl-sm"
          }`}
        >
          {message.text}
        </div>
      </div>
    </div>
  );
}

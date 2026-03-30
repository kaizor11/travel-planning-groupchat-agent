"use client";

import { useEffect, useRef, useState } from "react";
import { subscribeToMessages, TripMessage } from "@/lib/firestore/trips";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  tripId: string;
  currentUserId: string;
}

export function MessageList({ tripId, currentUserId }: MessageListProps) {
  const [messages, setMessages] = useState<TripMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsub = subscribeToMessages(tripId, (msgs) => {
      setMessages(msgs);
    });
    return () => unsub();
  }, [tripId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
        No messages yet. Drop a travel link to get started!
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          tripId={tripId}
          currentUserId={currentUserId}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

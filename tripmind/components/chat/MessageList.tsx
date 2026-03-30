"use client";

import { useEffect, useRef, useState } from "react";
import { subscribeToMessages, TripMessage } from "@/lib/firestore/trips";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  tripId: string;
  currentUserId: string;
}

function formatTimestamp(ts: { seconds: number } | null | undefined): string {
  if (!ts?.seconds) return "";
  const d = new Date(ts.seconds * 1000);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = diffMs / 60000;

  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${Math.floor(diffMin)}m ago`;

  const isToday = d.toDateString() === now.toDateString();
  const timeStr = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (isToday) return timeStr;

  return d.toLocaleDateString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
}

// Show a timestamp divider if >5 minutes passed since the previous message
function shouldShowTimestamp(
  current: TripMessage,
  previous: TripMessage | undefined
): boolean {
  if (!previous) return true;
  const curTs = (current.timestamp as { seconds?: number } | null)?.seconds ?? 0;
  const prevTs = (previous.timestamp as { seconds?: number } | null)?.seconds ?? 0;
  return curTs - prevTs > 300; // 5 minutes
}

// Show tail only on the last message in a consecutive run from the same sender
function shouldShowTail(messages: TripMessage[], index: number): boolean {
  const next = messages[index + 1];
  if (!next) return true;
  return next.senderId !== messages[index].senderId;
}

function shouldShowSender(messages: TripMessage[], index: number): boolean {
  const prev = messages[index - 1];
  if (!prev) return true;
  return prev.senderId !== messages[index].senderId;
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
      <div className="im-messages flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center px-6">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center text-3xl shadow-sm"
            style={{ background: "linear-gradient(135deg, #5856D6, #007AFF)" }}
          >
            ✈️
          </div>
          <p className="text-[15px] font-semibold text-black">TripMind</p>
          <p className="text-[13px] leading-relaxed" style={{ color: "#8E8E93", maxWidth: 220 }}>
            Drop a travel link to start building your group wish pool.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="im-messages">
      <div className="pt-1 pb-2">
        {messages.map((msg, i) => (
          <div key={msg.id}>
            {/* Timestamp divider */}
            {shouldShowTimestamp(msg, messages[i - 1]) && (
              <div className="im-timestamp">
                {formatTimestamp(msg.timestamp as { seconds: number } | null)}
              </div>
            )}

            <MessageBubble
              message={msg}
              tripId={tripId}
              currentUserId={currentUserId}
              showSender={shouldShowSender(messages, i)}
              showTail={shouldShowTail(messages, i)}
            />

            {/* "Delivered" receipt below last sent message */}
            {msg.senderId === currentUserId &&
              i === messages.length - 1 && (
                <p
                  className="text-right pr-4 mt-0.5"
                  style={{ fontSize: 11, color: "#8E8E93" }}
                >
                  Delivered
                </p>
              )}
          </div>
        ))}
      </div>
      <div ref={bottomRef} />
    </div>
  );
}

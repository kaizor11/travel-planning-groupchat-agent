"use client";

import { useState, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { addMessage } from "@/lib/firestore/trips";

const URL_REGEX = /https?:\/\/[^\s]+/;

interface ChatInputProps {
  tripId: string;
  currentUserId: string;
}

export function ChatInput({ tripId, currentUserId }: ChatInputProps) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setText("");

    try {
      // Write the user's message to Firestore first
      const urlMatch = trimmed.match(URL_REGEX);
      await addMessage(tripId, {
        senderId: currentUserId,
        text: trimmed,
        type: "user",
        attachedUrl: urlMatch?.[0],
      });

      // If a URL was detected, trigger AI parsing
      if (urlMatch) {
        await fetch("/api/ai/parse-content", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: urlMatch[0],
            text: trimmed !== urlMatch[0] ? trimmed.replace(urlMatch[0], "").trim() : undefined,
            tripId,
            senderId: currentUserId,
          }),
        });
      }
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="border-t border-border px-4 py-3 flex gap-2 items-end">
      <textarea
        className="flex-1 resize-none rounded-xl border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring min-h-[40px] max-h-32"
        placeholder="Message or drop a travel link…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        disabled={sending}
      />
      <Button
        size="sm"
        onClick={handleSend}
        disabled={!text.trim() || sending}
        className="shrink-0"
      >
        Send
      </Button>
    </div>
  );
}

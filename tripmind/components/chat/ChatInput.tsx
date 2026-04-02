"use client";

import { useState, KeyboardEvent, useRef, useEffect } from "react";
import { addMessage } from "@/lib/firestore/trips";
import { Plus, ArrowUp } from "lucide-react";

const URL_REGEX = /https?:\/\/[^\s]+/;

interface ChatInputProps {
  tripId: string;
  currentUserId: string;
}

export function ChatInput({ tripId, currentUserId }: ChatInputProps) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "22px";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [text]);

  const hasText = text.trim().length > 0;

  async function handleSend() {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setText("");
    if (textareaRef.current) textareaRef.current.style.height = "22px";

    try {
      const urlMatch = trimmed.match(URL_REGEX);
      const msg: Parameters<typeof addMessage>[1] = {
        senderId: currentUserId,
        text: trimmed,
        type: "user",
      };
      if (urlMatch) msg.attachedUrl = urlMatch[0];
      await addMessage(tripId, msg);

      if (urlMatch) {
        const res = await fetch("/api/ai/parse-content", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: urlMatch[0],
            text:
              trimmed !== urlMatch[0]
                ? trimmed.replace(urlMatch[0], "").trim()
                : undefined,
            tripId,
            senderId: currentUserId,
          }),
        });
        if (!res.ok) {
          console.error("[parse-content] failed:", await res.text());
        }
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
    <div className="im-input-bar">
      {/* + / Apps button */}
      <button className="im-app-btn" aria-label="More">
        <Plus size={22} strokeWidth={2} />
      </button>

      {/* Pill input */}
      <div className="im-input-pill">
        <textarea
          ref={textareaRef}
          rows={1}
          placeholder="iMessage"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
          style={{ height: 22 }}
        />
      </div>

      {/* Send button */}
      <button
        className={`im-send-btn ${hasText && !sending ? "active" : "inactive"}`}
        onClick={handleSend}
        disabled={!hasText || sending}
        aria-label="Send"
      >
        <ArrowUp
          size={17}
          strokeWidth={3}
          color="#fff"
          style={{ marginTop: 1 }}
        />
      </button>
    </div>
  );
}

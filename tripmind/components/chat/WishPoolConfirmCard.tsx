"use client";

import { addWishPoolEntry } from "@/lib/firestore/trips";
import { useState } from "react";
import { MapPin } from "lucide-react";

interface ParsedData {
  destination: string;
  tags: string[];
  estimatedCost?: string;
  confidence: number;
}

interface WishPoolConfirmCardProps {
  tripId: string;
  senderId: string;
  parsedData: ParsedData;
  sourceUrl?: string;
}

const COST_EMOJI: Record<string, string> = {
  budget: "💸",
  "mid-range": "💰",
  luxury: "💎",
};

export function WishPoolConfirmCard({
  tripId,
  senderId,
  parsedData,
  sourceUrl,
}: WishPoolConfirmCardProps) {
  const [confirmed, setConfirmed] = useState<"yes" | "no" | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleYes() {
    setLoading(true);
    try {
      await addWishPoolEntry(tripId, {
        submittedBy: senderId,
        destination: parsedData.destination,
        tags: parsedData.tags,
        estimatedCost: parsedData.estimatedCost,
        sourceUrl,
      });
      setConfirmed("yes");
    } finally {
      setLoading(false);
    }
  }

  if (confirmed === "yes") {
    return (
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-2xl text-white text-[13px] font-medium"
        style={{ background: "linear-gradient(135deg, #34C759, #30B050)", maxWidth: 260 }}
      >
        <span>✓</span>
        <span>{parsedData.destination} added to wish pool</span>
      </div>
    );
  }

  if (confirmed === "no") {
    return (
      <div
        className="px-3 py-2 rounded-2xl text-[13px]"
        style={{ background: "rgba(0,0,0,0.06)", color: "#8E8E93", maxWidth: 260 }}
      >
        Skipped
      </div>
    );
  }

  return (
    <div className="im-wishpool-card">
      {/* Card header — gradient strip */}
      <div className="im-wishpool-header">
        <div className="flex items-start gap-2">
          <MapPin size={15} className="text-white/80 mt-0.5 flex-shrink-0" />
          <div className="flex flex-col gap-0.5">
            <p className="text-white font-semibold text-[14px] leading-snug">
              {parsedData.destination}
            </p>
            {parsedData.tags.length > 0 && (
              <p className="text-white/75 text-[11px] leading-relaxed">
                {parsedData.tags.join(" · ")}
              </p>
            )}
          </div>
          {parsedData.estimatedCost && (
            <span className="ml-auto text-[15px]" title={parsedData.estimatedCost}>
              {COST_EMOJI[parsedData.estimatedCost.toLowerCase()] ?? "✈️"}
            </span>
          )}
        </div>
      </div>

      {/* Prompt text */}
      <div className="px-4 py-2.5">
        <p className="text-[13px] text-black/70">Add to the group wish pool?</p>
      </div>

      {/* Action buttons */}
      <div className="im-wishpool-actions">
        <button
          className="im-wishpool-btn yes"
          onClick={handleYes}
          disabled={loading}
        >
          {loading ? "Adding…" : "Add"}
        </button>
        <div className="im-wishpool-btn-divider" />
        <button
          className="im-wishpool-btn no"
          onClick={() => setConfirmed("no")}
          disabled={loading}
        >
          Skip
        </button>
      </div>
    </div>
  );
}

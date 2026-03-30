"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { addWishPoolEntry } from "@/lib/firestore/trips";
import { useState } from "react";

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

  function handleNo() {
    setConfirmed("no");
  }

  if (confirmed === "yes") {
    return (
      <p className="text-sm text-green-600 font-medium">
        Added {parsedData.destination} to the wish pool.
      </p>
    );
  }

  if (confirmed === "no") {
    return (
      <p className="text-sm text-muted-foreground">Skipped.</p>
    );
  }

  return (
    <Card className="max-w-sm border border-border">
      <CardContent className="pt-4 pb-3 space-y-3">
        <div>
          <p className="font-semibold text-sm">{parsedData.destination}</p>
          <p className="text-xs text-muted-foreground">
            {parsedData.tags.join(" · ")}
            {parsedData.estimatedCost ? ` · ${parsedData.estimatedCost}` : ""}
          </p>
        </div>
        <p className="text-sm">Add to wish pool?</p>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleYes} disabled={loading}>
            Yes
          </Button>
          <Button size="sm" variant="outline" onClick={handleNo} disabled={loading}>
            No
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

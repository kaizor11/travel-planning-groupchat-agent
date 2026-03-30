import { NextRequest, NextResponse } from "next/server";
import { anthropic } from "@/lib/anthropic";
import { getAdminDb } from "@/lib/firebase-admin";
import { FieldValue } from "firebase-admin/firestore";

interface ParsedContent {
  destination: string;
  tags: string[];
  estimatedCost?: string;
  confidence: number;
}

const SYSTEM_PROMPT = `You are a travel content parser. When given a URL or text, extract travel intent and return ONLY valid JSON with no markdown, no explanation.

JSON shape:
{
  "destination": "string — specific city or region, empty string if none found",
  "tags": ["array", "of", "activity/vibe", "tags"],
  "estimatedCost": "optional string like 'budget', 'mid-range', 'luxury'",
  "confidence": 0.0
}

confidence is 0–1. Set below 0.7 if destination is unclear or content is not clearly travel-related.
Tags should describe: activity type (beach, hiking, city, food, culture, nightlife), vibe (relaxed, adventurous, luxury, budget).`;

export async function POST(req: NextRequest) {
  try {
    const { url, text, tripId, senderId } = await req.json();

    if (!tripId || !senderId) {
      return NextResponse.json(
        { error: "tripId and senderId are required" },
        { status: 400 }
      );
    }

    const userContent = url
      ? `URL: ${url}${text ? `\nCaption: ${text}` : ""}`
      : text;

    if (!userContent) {
      return NextResponse.json({ error: "url or text is required" }, { status: 400 });
    }

    const message = await anthropic.messages.create({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: userContent }],
    });

    const rawText =
      message.content[0].type === "text" ? message.content[0].text : "";

    let parsed: ParsedContent;
    try {
      parsed = JSON.parse(rawText);
    } catch {
      return NextResponse.json({ error: "AI returned invalid JSON" }, { status: 500 });
    }

    // Write wishpool_confirm message to Firestore (server-side, using Admin SDK)
    const messagesRef = getAdminDb()
      .collection("trips")
      .doc(tripId)
      .collection("messages");

    await messagesRef.add({
      senderId: "ai",
      text: parsed.confidence >= 0.7
        ? `I found a travel idea: **${parsed.destination}** (${parsed.tags.join(", ")}${parsed.estimatedCost ? `, ${parsed.estimatedCost}` : ""}). Add it to the wish pool?`
        : "I couldn't extract a clear travel destination from that link. Can you paste the caption or description?",
      timestamp: FieldValue.serverTimestamp(),
      type: parsed.confidence >= 0.7 ? "wishpool_confirm" : "ai",
      attachedUrl: url ?? undefined,
      parsedData: parsed.confidence >= 0.7 ? parsed : undefined,
    });

    return NextResponse.json({ ...parsed, needsConfirmation: parsed.confidence < 0.7 });
  } catch (err) {
    console.error("[parse-content] error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}

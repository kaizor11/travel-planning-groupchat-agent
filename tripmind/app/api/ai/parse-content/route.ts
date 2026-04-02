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

const SYSTEM_PROMPT = `You are a travel content parser. When given a URL or text, extract travel intent and return ONLY valid JSON with no markdown fences, no explanation, no extra text — raw JSON only.

JSON shape:
{
  "destination": "string — specific city or region, empty string if none found",
  "tags": ["array", "of", "activity/vibe", "tags"],
  "estimatedCost": "optional string: 'budget', 'mid-range', or 'luxury'",
  "confidence": 0.0
}

confidence is 0–1. Set below 0.7 if:
- The URL is a social media link (Instagram, TikTok, YouTube) and no caption was provided — you cannot see the video/photo content
- The destination is unclear or the content is not travel-related

Tags should describe: activity type (beach, hiking, city, food, culture, nightlife), vibe (relaxed, adventurous, luxury, budget).`;

function stripCodeFences(raw: string): string {
  return raw
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
}

function omitUndefined<T extends Record<string, unknown>>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined)
  ) as Partial<T>;
}

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
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: userContent }],
    });

    const rawText =
      message.content[0].type === "text" ? message.content[0].text : "";

    let parsed: ParsedContent;
    try {
      parsed = JSON.parse(stripCodeFences(rawText));
    } catch {
      console.error("[parse-content] JSON parse failed. Raw response:", rawText);
      return NextResponse.json({ error: "AI returned invalid JSON" }, { status: 500 });
    }

    const messagesRef = getAdminDb()
      .collection("trips")
      .doc(tripId)
      .collection("messages");

    const isSocialMediaUrl =
      url && /instagram|tiktok|youtube|youtu\.be|twitter|x\.com/i.test(url);

    const highConfidence = parsed.confidence >= 0.7;

    let aiText: string;
    if (highConfidence) {
      aiText = `Found a travel idea: **${parsed.destination}** (${parsed.tags.join(", ")}${parsed.estimatedCost ? `, ${parsed.estimatedCost}` : ""}). Add it to the wish pool?`;
    } else if (isSocialMediaUrl) {
      aiText = "I can see the link but can't view the content — can you paste the caption or describe where this is? I'll save it to the wish pool.";
    } else {
      aiText = "I couldn't extract a clear travel destination from that link. Can you paste the caption or describe it?";
    }

    await messagesRef.add(
      omitUndefined({
        senderId: "ai",
        text: aiText,
        timestamp: FieldValue.serverTimestamp(),
        type: highConfidence ? "wishpool_confirm" : "ai",
        attachedUrl: url ?? undefined,
        parsedData: highConfidence ? parsed : undefined,
      })
    );

    return NextResponse.json({ ...parsed, needsConfirmation: !highConfidence });
  } catch (err) {
    console.error("[parse-content] error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}

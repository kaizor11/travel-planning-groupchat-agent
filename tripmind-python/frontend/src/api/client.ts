// HTTP client: typed fetch wrappers for all backend API endpoints and SSE stream factory.
import type { Message } from '../types/message'

export async function getMessages(tripId: string): Promise<{ messages: Message[]; current_user_id: string }> {
  const res = await fetch(`/api/trips/${tripId}`)
  if (!res.ok) throw new Error('Failed to load messages')
  return res.json()
}

export async function sendMessage(tripId: string, text: string, senderId: string): Promise<void> {
  const res = await fetch(`/api/trips/${tripId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, sender_id: senderId }),
  })
  if (!res.ok) throw new Error('Failed to send message')
}

export async function confirmWishpool(
  tripId: string,
  action: 'add' | 'skip',
  destination: string,
  tags: string[],
  estimatedCost: string | null,
  sourceUrl: string | null,
  submittedBy: string,
): Promise<void> {
  const res = await fetch(`/api/trips/${tripId}/wishpool`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action,
      destination,
      tags,
      estimated_cost: estimatedCost,
      source_url: sourceUrl,
      submitted_by: submittedBy,
    }),
  })
  if (!res.ok) throw new Error('Failed to confirm wishpool')
}

export function createSSEStream(tripId: string): EventSource {
  // Connect directly to FastAPI (bypass Vite proxy) — the proxy buffers small SSE chunks
  // and only flushes them when the connection closes, breaking real-time delivery.
  // FastAPI already has CORS configured for http://localhost:5173 so this works in dev.
  return new EventSource(`http://localhost:8000/api/trips/${tripId}/stream`)
}

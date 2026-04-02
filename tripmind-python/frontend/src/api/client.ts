// HTTP client: typed fetch wrappers for all backend API endpoints and SSE stream factory.
import type { Message } from '../types/message'

// In dev: VITE_API_URL is unset.
//   - Fetch calls use '' so relative /api/... paths go through the Vite proxy.
//   - SSE uses 'http://localhost:8000' directly to bypass the Vite proxy, which buffers
//     SSE chunks and breaks real-time delivery.
// In production (Vercel): VITE_API_URL is the Render backend URL for both.
const API_BASE = import.meta.env.VITE_API_URL ?? ''
const SSE_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function getMessages(tripId: string): Promise<{ messages: Message[]; current_user_id: string }> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}`)
  if (!res.ok) throw new Error('Failed to load messages')
  return res.json()
}

export async function sendMessage(tripId: string, text: string, senderId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/messages`, {
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
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/wishpool`, {
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
  return new EventSource(`${SSE_BASE}/api/trips/${tripId}/stream`)
}

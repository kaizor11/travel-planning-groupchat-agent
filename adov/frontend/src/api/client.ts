// HTTP client: typed fetch wrappers for all backend API endpoints and SSE stream factory.
// All mutating endpoints require an idToken (Firebase ID token) for auth.
import type { Message } from '../types/message'

// In dev: VITE_API_URL is unset.
//   - Fetch calls use '' so relative /api/... paths go through the Vite proxy.
//   - SSE uses 'http://localhost:8000' directly to bypass the Vite proxy, which buffers
//     SSE chunks and breaks real-time delivery.
// In production (Vercel): VITE_API_URL is the Render backend URL for both.
const API_BASE = import.meta.env.VITE_API_URL ?? ''
const SSE_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function authHeaders(idToken: string) {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${idToken}` }
}

// ── Trip messages ─────────────────────────────────────────────────────────────

export async function getMessages(
  tripId: string,
  idToken: string,
): Promise<{ messages: Message[]; current_user_id: string; current_user_name: string }> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}`, {
    headers: { Authorization: `Bearer ${idToken}` },
  })
  if (!res.ok) throw new Error('Failed to load messages')
  return res.json()
}

export async function sendMessage(
  tripId: string,
  text: string,
  senderName: string,
  idToken: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/messages`, {
    method: 'POST',
    headers: authHeaders(idToken),
    body: JSON.stringify({ text, sender_name: senderName }),
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
  idToken: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/wishpool`, {
    method: 'POST',
    headers: authHeaders(idToken),
    body: JSON.stringify({
      action,
      destination,
      tags,
      estimated_cost: estimatedCost,
      source_url: sourceUrl,
    }),
  })
  if (!res.ok) throw new Error('Failed to confirm wishpool')
}

export function createSSEStream(tripId: string): EventSource {
  return new EventSource(`${SSE_BASE}/api/trips/${tripId}/stream`)
}

// ── Group invite ──────────────────────────────────────────────────────────────

export async function getInviteInfo(
  tripId: string,
): Promise<{ member_count: number; exists: boolean }> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/invite`)
  if (!res.ok) throw new Error('Failed to get invite info')
  return res.json()
}

export async function joinTrip(tripId: string, idToken: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/join`, {
    method: 'POST',
    headers: authHeaders(idToken),
  })
  if (!res.ok) throw new Error('Failed to join trip')
}

// ── User profile ──────────────────────────────────────────────────────────────

export interface UserProfile {
  name?: string
  email?: string
  avatarUrl?: string
  budgetMin?: number
  budgetMax?: number
  preferences?: string[]
  tripDurationMin?: number
  tripDurationMax?: number
}

export async function getProfile(idToken: string): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/api/users/me`, {
    headers: { Authorization: `Bearer ${idToken}` },
  })
  if (!res.ok) throw new Error('Failed to load profile')
  return res.json()
}

export async function updateProfile(data: Partial<UserProfile>, idToken: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/users/me`, {
    method: 'PUT',
    headers: authHeaders(idToken),
    body: JSON.stringify({
      budget_min: data.budgetMin,
      budget_max: data.budgetMax,
      preferences: data.preferences,
      trip_duration_min: data.tripDurationMin,
      trip_duration_max: data.tripDurationMax,
    }),
  })
  if (!res.ok) throw new Error('Failed to update profile')
}

export async function updateCalendarToken(accessToken: string, idToken: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/users/me/calendar-token`, {
    method: 'PUT',
    headers: authHeaders(idToken),
    body: JSON.stringify({ access_token: accessToken }),
  })
  if (!res.ok) throw new Error('Failed to store calendar token')
}

// ── Calendar free/busy ────────────────────────────────────────────────────────

export async function getFreeBusy(
  tripId: string,
  timeMin: string,
  timeMax: string,
  idToken: string,
): Promise<{ windows: { start: string; end: string }[]; membersChecked: number }> {
  const res = await fetch(`${API_BASE}/api/calendar/freebusy`, {
    method: 'POST',
    headers: authHeaders(idToken),
    body: JSON.stringify({ trip_id: tripId, time_min: timeMin, time_max: timeMax }),
  })
  if (!res.ok) throw new Error('Failed to get free/busy windows')
  return res.json()
}

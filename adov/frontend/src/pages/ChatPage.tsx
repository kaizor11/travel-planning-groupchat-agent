// Main chat page: owns message state, manages SSE subscription, and composes all chat UI components.
// Uses the authenticated Firebase user for identity — no more hardcoded TEMP_USER_ID.
import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import type { Message } from '../types/message'
import { getMessages, sendMessage, createSSEStream } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import ChatHeader from '../components/ChatHeader'
import ChatInput from '../components/ChatInput'
import MessageBubble from '../components/MessageBubble'
import ProfileDrawer from '../components/ProfileDrawer'

export default function ChatPage() {
  const { tripId } = useParams<{ tripId: string }>()
  const { user, idToken } = useAuth()
  const [messages, setMessages] = useState<Message[]>([])
  const [showProfile, setShowProfile] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  // Ref so the SSE closure always reads the latest currentUserId without re-subscribing
  const currentUserIdRef = useRef('')

  const currentUserId = user?.uid ?? ''

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Load initial messages from backend (requires auth)
  useEffect(() => {
    if (!tripId || !idToken) return
    getMessages(tripId, idToken).then(({ messages: msgs }) => {
      setMessages(msgs)
      currentUserIdRef.current = user?.uid ?? ''
    })
  }, [tripId, idToken, user?.uid])

  // Keep ref in sync with user changes
  useEffect(() => {
    currentUserIdRef.current = currentUserId
  }, [currentUserId])

  // Scroll to bottom whenever messages change
  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  // SSE subscription with auto-reconnect (handles backend starting after frontend)
  useEffect(() => {
    if (!tripId) return
    let source: EventSource
    let retryTimer: ReturnType<typeof setTimeout>

    const connect = () => {
      source = createSSEStream(tripId)
      source.onmessage = (e) => {
        console.log('[SSE] received:', e.data)
        try {
          const msg: Message = JSON.parse(e.data)
          console.log('[SSE] parsed:', msg.type, msg.senderId)
          // Skip own messages — already shown optimistically on send
          if (msg.senderId === currentUserIdRef.current) {
            console.log('[SSE] skipped (own message)')
            return
          }
          setMessages(prev => [...prev, msg])
        } catch (err) {
          console.error('[SSE] parse error:', err, '| raw:', e.data)
        }
      }
      source.onerror = (e) => {
        console.error('[SSE] connection error:', e)
        source.close()
        retryTimer = setTimeout(connect, 2000)
      }
    }

    connect()
    return () => {
      source?.close()
      clearTimeout(retryTimer)
    }
  }, [tripId])

  const handleSend = useCallback(async (text: string) => {
    if (!tripId || !currentUserId || !idToken) return

    const senderName = user?.displayName ?? ''

    // Optimistically append the sent message so the UI reacts immediately
    const tempMsg: Message = {
      id: `temp-${Date.now()}`,
      type: 'user',
      senderId: currentUserId,
      senderName,
      text,
    }
    setMessages(prev => [...prev, tempMsg])

    try {
      await sendMessage(tripId, text, senderName, idToken)
    } catch (err) {
      console.error('[TripMind] send failed:', err)
      // Roll back optimistic message on failure
      setMessages(prev => prev.filter(m => m.id !== tempMsg.id))
    }
  }, [tripId, currentUserId, idToken, user?.displayName])

  if (!tripId) return null

  return (
    <div
      data-user-id={currentUserId || undefined}
      style={{ display: 'flex', flexDirection: 'column', height: '100dvh', overflow: 'hidden' }}
    >
      <ChatHeader
        tripId={tripId}
        onProfileOpen={() => setShowProfile(true)}
      />

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 0 4px',
          background: '#F2F2F7',
          scrollbarWidth: 'none',
        }}
      >
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3 text-center px-6 py-12">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center text-3xl shadow-sm"
                style={{ background: 'linear-gradient(135deg,#5856D6,#007AFF)' }}
              >
                ✈️
              </div>
              <p className="font-semibold text-black" style={{ fontSize: '15px' }}>Adov</p>
              <p style={{ fontSize: '13px', color: '#8E8E93', maxWidth: '220px', lineHeight: '1.5' }}>
                Drop a travel link or start chatting.
              </p>
            </div>
          </div>
        ) : (
          messages.map(msg => (
            <MessageBubble
              key={msg.id}
              message={msg}
              currentUserId={currentUserId}
              tripId={tripId}
              idToken={idToken ?? ''}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={handleSend} />

      {showProfile && idToken && (
        <ProfileDrawer
          user={user}
          idToken={idToken}
          onClose={() => setShowProfile(false)}
        />
      )}
    </div>
  )
}

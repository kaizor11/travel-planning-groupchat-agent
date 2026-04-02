// Main chat page: owns message state, manages SSE subscription, and composes all chat UI components.
import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import type { Message } from '../types/message'
import { getMessages, sendMessage, createSSEStream } from '../api/client'
import ChatHeader from '../components/ChatHeader'
import ChatInput from '../components/ChatInput'
import MessageBubble from '../components/MessageBubble'

export default function ChatPage() {
  const { tripId } = useParams<{ tripId: string }>()
  const [messages, setMessages] = useState<Message[]>([])
  const [currentUserId, setCurrentUserId] = useState<string>('')
  const bottomRef = useRef<HTMLDivElement>(null)
  // Ref so the SSE closure always reads the latest currentUserId without re-subscribing
  const currentUserIdRef = useRef('')

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Load initial messages from backend
  useEffect(() => {
    if (!tripId) return
    getMessages(tripId).then(({ messages: msgs, current_user_id }) => {
      setMessages(msgs)
      setCurrentUserId(current_user_id)
      currentUserIdRef.current = current_user_id
    })
  }, [tripId])

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
    if (!tripId || !currentUserId) return

    // Optimistically append the sent message so the UI reacts immediately
    const tempMsg: Message = {
      id: `temp-${Date.now()}`,
      type: 'user',
      senderId: currentUserId,
      text,
    }
    setMessages(prev => [...prev, tempMsg])

    try {
      await sendMessage(tripId, text, currentUserId)
    } catch (err) {
      console.error('[TripMind] send failed:', err)
      // Roll back optimistic message on failure
      setMessages(prev => prev.filter(m => m.id !== tempMsg.id))
    }
  }, [tripId, currentUserId])

  if (!tripId) return null

  return (
    <div data-user-id={currentUserId || undefined} style={{ display: 'flex', flexDirection: 'column', height: '100dvh', overflow: 'hidden' }}>
      <ChatHeader tripId={tripId} />

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
              <p className="font-semibold text-black" style={{ fontSize: '15px' }}>TripMind</p>
              <p style={{ fontSize: '13px', color: '#8E8E93', maxWidth: '220px', lineHeight: '1.5' }}>
                Drop a travel link to start building your group wish pool.
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
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={handleSend} />
    </div>
  )
}

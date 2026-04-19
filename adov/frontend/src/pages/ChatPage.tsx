// Main chat page: owns message state, manages SSE subscription, and composes all chat UI components.
// Uses the authenticated Firebase user for identity — no more hardcoded TEMP_USER_ID.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { signOut } from 'firebase/auth'
import { auth } from '../lib/firebase'
import type { Message } from '../types/message'
import { createSSEStream, getMessages, resetTrip, sendImageMessage, sendMessage } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import ChatHeader from '../components/ChatHeader'
import ChatInput from '../components/ChatInput'
import MessageBubble from '../components/MessageBubble'
import ProfileDrawer from '../components/ProfileDrawer'

function mergeIncomingMessage(prev: Message[], msg: Message, currentUserId: string): Message[] {
  const existingIndex = prev.findIndex(item => item.id === msg.id)
  if (existingIndex >= 0) {
    const next = [...prev]
    next[existingIndex] = { ...next[existingIndex], ...msg }
    return next
  }

  if (msg.senderId === currentUserId) {
    return prev
  }

  return [...prev, msg]
}

export default function ChatPage() {
  const { tripId } = useParams<{ tripId: string }>()
  const navigate = useNavigate()
  const { user, idToken } = useAuth()
  const [messages, setMessages] = useState<Message[]>([])
  const [showProfile, setShowProfile] = useState(false)
  const [screenshotEnabled, setScreenshotEnabled] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const currentUserIdRef = useRef('')
  const idTokenRef = useRef<string | null>(null)

  const currentUserId = user?.uid ?? ''

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    if (!tripId || !idToken) return
    getMessages(tripId, idToken)
      .then(({ messages: msgs, features }) => {
        setMessages(msgs)
        setScreenshotEnabled(Boolean(features?.screenshotProcessingEnabled))
        currentUserIdRef.current = user?.uid ?? ''
      })
      .catch(err => console.error('[ChatPage] initial messages fetch failed:', err))
  }, [tripId, idToken, user?.uid])

  useEffect(() => {
    currentUserIdRef.current = currentUserId
  }, [currentUserId])

  useEffect(() => {
    idTokenRef.current = idToken
  }, [idToken])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  useEffect(() => {
    if (!tripId) return
    let source: EventSource
    let retryTimer: ReturnType<typeof setTimeout>

    const connect = () => {
      source = createSSEStream(tripId)
      source.onmessage = (e) => {
        try {
          const msg: Message = JSON.parse(e.data)
          if (msg.type === 'reset') {
            source.close()
            signOut(auth).finally(() => navigate(`/join/${tripId}`))
            return
          }
          setMessages(prev => mergeIncomingMessage(prev, msg, currentUserIdRef.current))
        } catch (err) {
          console.error('[SSE] parse error:', err, '| raw:', e.data)
        }
      }
      source.onerror = (e) => {
        console.error('[SSE] connection error:', e)
        source.close()
        const token = idTokenRef.current
        if (tripId && token) {
          getMessages(tripId, token)
            .then(({ messages: serverMsgs, features }) => {
              setScreenshotEnabled(Boolean(features?.screenshotProcessingEnabled))
              setMessages(prev => {
                const serverIds = new Set(serverMsgs.map(m => m.id))
                const optimistic = prev.filter(m => !serverIds.has(m.id))
                return [...serverMsgs, ...optimistic]
              })
            })
            .catch(err => console.error('[SSE] refetch after reconnect failed:', err))
        }
        retryTimer = setTimeout(connect, 2000)
      }
    }

    connect()
    return () => {
      source?.close()
      clearTimeout(retryTimer)
    }
  }, [tripId, navigate])

  const handleReset = useCallback(async () => {
    if (!tripId || !idToken) return
    if (!window.confirm('Reset this session? This clears all messages, calendar connections, and preferences.')) return
    await resetTrip(tripId, idToken)
    await signOut(auth)
    navigate(`/join/${tripId}`)
  }, [tripId, idToken, navigate])

  const handleSend = useCallback(async (text: string) => {
    if (!tripId || !currentUserId || !idToken) return

    const senderName = user?.displayName ?? ''
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
      setMessages(prev => prev.filter(m => m.id !== tempMsg.id))
    }
  }, [tripId, currentUserId, idToken, user?.displayName])

  const handleSendImage = useCallback(async (file: File, caption: string, clientTempId: string) => {
    if (!tripId || !currentUserId || !idToken) return

    const senderName = user?.displayName ?? ''
    const previewUrl = URL.createObjectURL(file)
    const tempMsg: Message = {
      id: clientTempId,
      type: 'user',
      senderId: currentUserId,
      senderName,
      text: caption,
      imageUrl: previewUrl,
      imageName: file.name,
      imageMimeType: file.type,
      analysisStatus: 'pending',
      imageAnalysis: null,
      analysisReplyMessageId: null,
    }
    setMessages(prev => [...prev, tempMsg])

    try {
      const created = await sendImageMessage(tripId, file, caption, senderName, idToken)
      setMessages(prev => prev.map(msg => (msg.id === clientTempId ? created : msg)))
    } catch (err) {
      console.error('[TripMind] image send failed:', err)
      setMessages(prev => prev.filter(msg => msg.id !== clientTempId))
    } finally {
      URL.revokeObjectURL(previewUrl)
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
        onReset={handleReset}
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
                {screenshotEnabled ? 'Drop a travel link, share a screenshot, or start chatting.' : 'Drop a travel link or start chatting.'}
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

      <ChatInput
        onSend={handleSend}
        onSendImage={handleSendImage}
        screenshotEnabled={screenshotEnabled}
      />

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

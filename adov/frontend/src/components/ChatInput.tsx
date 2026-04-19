// Pill-shaped iMessage-style input bar with auto-growing textarea and animated send button.
import { useRef, useState } from 'react'

interface ChatInputProps {
  onSend: (text: string) => void
  onSendImage?: (file: File, caption: string, clientTempId: string) => Promise<void>
  screenshotEnabled?: boolean
}

export default function ChatInput({ onSend, onSendImage, screenshotEnabled = false }: ChatInputProps) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = '22px'
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
    }
  }

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = '22px'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleMoreClick = () => {
    fileInputRef.current?.click()
  }

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !onSendImage) return

    const caption = text.trim()
    const clientTempId = `temp-image-${Date.now()}`
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = '22px'
    }

    try {
      await onSendImage(file, caption, clientTempId)
    } finally {
      e.target.value = ''
    }
  }

  const hasText = text.trim().length > 0

  return (
    <div className="im-input-bar">
      {screenshotEnabled && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={handleImageSelect}
            style={{ display: 'none' }}
          />
          <button type="button" className="im-app-btn" aria-label="More" onClick={handleMoreClick}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </>
      )}
      <div className="im-input-pill">
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Message..."
          aria-label="Message input"
        />
      </div>
      <button
        type="button"
        onClick={handleSend}
        className={`im-send-btn ${hasText ? 'active' : 'inactive'}`}
        aria-label="Send"
      >
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: '1px' }}>
          <line x1="12" y1="19" x2="12" y2="5" />
          <polyline points="5 12 12 5 19 12" />
        </svg>
      </button>
    </div>
  )
}

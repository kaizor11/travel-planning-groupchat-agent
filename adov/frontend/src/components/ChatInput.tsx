// Pill-shaped iMessage-style input bar with auto-growing textarea and animated send button.
// The + button opens a file picker for image uploads (PNG, JPEG, WebP).
import { useRef, useState } from 'react'

interface ChatInputProps {
  onSend: (text: string) => void
  onSendImage: (file: File, caption: string) => void
}

export default function ChatInput({ onSend, onSendImage }: ChatInputProps) {
  const [text, setText] = useState('')
  const [pendingImage, setPendingImage] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPendingImage(file)
    setPreviewUrl(URL.createObjectURL(file))
    // Reset input so the same file can be re-selected later
    e.target.value = ''
  }

  const handleSend = () => {
    if (pendingImage) {
      onSendImage(pendingImage, text.trim())
      setPendingImage(null)
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
      setText('')
      if (textareaRef.current) textareaRef.current.style.height = '22px'
      return
    }
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
    if (textareaRef.current) textareaRef.current.style.height = '22px'
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const cancelImage = () => {
    setPendingImage(null)
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
  }

  const hasContent = text.trim().length > 0 || pendingImage !== null

  return (
    <div className="im-input-bar" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 0 }}>
      {pendingImage && previewUrl && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px 2px' }}>
          <img
            src={previewUrl}
            alt="preview"
            style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 8, flexShrink: 0 }}
          />
          <span style={{ fontSize: 12, color: '#8E8E93', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {pendingImage.name}
          </span>
          <button
            onClick={cancelImage}
            aria-label="Remove image"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#8E8E93', fontSize: 16, padding: '0 4px' }}
          >
            ✕
          </button>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 0, width: '100%' }}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <button
          className="im-app-btn"
          aria-label="Attach image"
          onClick={() => fileInputRef.current?.click()}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
        <div className="im-input-pill">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={pendingImage ? 'Add a caption…' : 'Message...'}
            aria-label="Message input"
          />
        </div>
        <button
          onClick={handleSend}
          className={`im-send-btn ${hasContent ? 'active' : 'inactive'}`}
          aria-label="Send"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: '1px' }}>
            <line x1="12" y1="19" x2="12" y2="5" />
            <polyline points="5 12 12 5 19 12" />
          </svg>
        </button>
      </div>
    </div>
  )
}

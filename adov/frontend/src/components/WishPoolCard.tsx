// Interactive "Add to wish pool?" confirmation card shown for high-confidence travel content.
import { useState } from 'react'
import type { Message } from '../types/message'
import { confirmWishpool } from '../api/client'

const COST_EMOJI: Record<string, string> = {
  budget: '💸',
  'mid-range': '💰',
  luxury: '💎',
}

interface WishPoolCardProps {
  message: Message
  tripId: string
  idToken: string
}

export default function WishPoolCard({ message, tripId, idToken }: WishPoolCardProps) {
  const [status, setStatus] = useState<'pending' | 'added' | 'skipped'>('pending')
  const pd = message.parsedData!

  const handleAdd = async () => {
    setStatus('added')
    await confirmWishpool(
      tripId,
      'add',
      pd.destination,
      pd.tags,
      pd.estimatedCost ?? null,
      message.attachedUrl ?? null,
      idToken,
    )
  }

  const handleSkip = () => {
    setStatus('skipped')
    confirmWishpool(tripId, 'skip', pd.destination, pd.tags, null, null, idToken)
  }

  const emoji = pd.estimatedCost ? (COST_EMOJI[pd.estimatedCost] ?? '') : ''
  const tags = (pd.tags ?? []).join(' · ')

  return (
    <div className="wishpool-card">
      <div className="wishpool-header">
        <div className="flex items-start gap-2">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: '2px', flexShrink: 0 }}>
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          <div>
            <p className="text-white font-semibold" style={{ fontSize: '14px', lineHeight: '1.3' }}>
              {pd.destination}
            </p>
            <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.75)', lineHeight: '1.4', marginTop: '2px' }}>
              {tags}
            </p>
          </div>
          <span className="ml-auto" style={{ fontSize: '15px' }}>{emoji}</span>
        </div>
      </div>
      <div style={{ padding: '10px 14px 8px' }}>
        <p style={{ fontSize: '13px', color: 'rgba(0,0,0,0.65)' }}>Add to the group wish pool?</p>
      </div>
      <div className="wishpool-actions">
        {status === 'pending' && (
          <>
            <button className="wishpool-btn add" onClick={handleAdd}>Add</button>
            <div className="wishpool-divider" />
            <button className="wishpool-btn skip" onClick={handleSkip}>Skip</button>
          </>
        )}
        {status === 'added' && (
          <div style={{ flex: 1, padding: '11px 14px', fontSize: '13px', color: '#34C759', fontWeight: 500 }}>
            ✓ Added to wish pool
          </div>
        )}
        {status === 'skipped' && (
          <div style={{ flex: 1, padding: '11px 14px', fontSize: '13px', color: '#8E8E93' }}>
            Skipped
          </div>
        )}
      </div>
    </div>
  )
}

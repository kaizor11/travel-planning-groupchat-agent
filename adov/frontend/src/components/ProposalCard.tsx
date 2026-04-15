// Renders a single trip proposal with destination, dates, cost, rationale, tradeoff,
// and yes/no/maybe vote buttons. Vote state is local until the SSE stream delivers the
// AI progress update confirming the vote was recorded.
import { useState } from 'react'
import type { ProposalData } from '../types/message'
import { castVote } from '../api/client'

interface ProposalCardProps {
  proposal: ProposalData
  tripId: string
  idToken: string
  currentUserId: string
}

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return iso
  }
}

export default function ProposalCard({ proposal, tripId, idToken, currentUserId }: ProposalCardProps) {
  const existingVote = proposal.votes?.[currentUserId] ?? null
  const [myVote, setMyVote] = useState<'yes' | 'no' | 'maybe' | null>(existingVote)
  const [voting, setVoting] = useState(false)

  // Compute tally from current votes (live until SSE pushes an update)
  const tally = { yes: 0, no: 0, maybe: 0 }
  for (const v of Object.values(proposal.votes ?? {})) {
    if (v in tally) tally[v as keyof typeof tally]++
  }
  const totalVotes = tally.yes + tally.no + tally.maybe

  const handleVote = async (vote: 'yes' | 'no' | 'maybe') => {
    if (voting || myVote === vote) return
    setVoting(true)
    try {
      await castVote(tripId, proposal.proposalId, vote, idToken)
      setMyVote(vote)
    } catch (err) {
      console.error('[ProposalCard] vote failed:', err)
    } finally {
      setVoting(false)
    }
  }

  const VOTE_OPTIONS: Array<{ key: 'yes' | 'no' | 'maybe'; label: string; emoji: string; activeColor: string }> = [
    { key: 'yes', label: 'Yes', emoji: '👍', activeColor: '#34C759' },
    { key: 'no', label: 'No', emoji: '👎', activeColor: '#FF3B30' },
    { key: 'maybe', label: 'Maybe', emoji: '🤔', activeColor: '#FF9500' },
  ]

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: '16px',
        padding: '16px',
        width: 'min(300px, 80vw)',
        boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}
    >
      {/* Destination + dates */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <span
          style={{
            fontSize: '16px',
            fontWeight: '700',
            color: '#000',
            lineHeight: 1.2,
          }}
        >
          {proposal.destination}
        </span>
        <span style={{ fontSize: '12px', color: '#8E8E93' }}>
          {formatDate(proposal.suggestedDates?.start)} — {formatDate(proposal.suggestedDates?.end)}
        </span>
      </div>

      {/* Cost */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <div
          style={{
            background: '#F2F2F7',
            borderRadius: '8px',
            padding: '6px 10px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            minWidth: '80px',
          }}
        >
          <span style={{ fontSize: '11px', color: '#8E8E93' }}>Est. per person</span>
          <span style={{ fontSize: '15px', fontWeight: '700', color: '#007AFF' }}>
            ${proposal.estimatedCostPerPerson?.toLocaleString()}
          </span>
        </div>
        {proposal.flightEstimate != null && (
          <div
            style={{
              background: '#F2F2F7',
              borderRadius: '8px',
              padding: '6px 10px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              minWidth: '72px',
            }}
          >
            <span style={{ fontSize: '11px', color: '#8E8E93' }}>Flights from</span>
            <span style={{ fontSize: '15px', fontWeight: '700', color: '#5856D6' }}>
              ${proposal.flightEstimate?.toLocaleString()}
            </span>
          </div>
        )}
      </div>

      {/* Rationale */}
      <p
        style={{
          fontSize: '13px',
          color: '#3C3C43',
          margin: 0,
          lineHeight: 1.5,
        }}
      >
        {proposal.rationale}
      </p>

      {/* Tradeoff */}
      <div
        style={{
          background: '#FFF3CD',
          borderRadius: '8px',
          padding: '8px 10px',
          display: 'flex',
          gap: '6px',
          alignItems: 'flex-start',
        }}
      >
        <span style={{ fontSize: '13px' }}>⚠️</span>
        <span style={{ fontSize: '12px', color: '#664D03', lineHeight: 1.4 }}>
          {proposal.tradeoff}
        </span>
      </div>

      {/* Vote buttons */}
      <div style={{ display: 'flex', gap: '6px' }}>
        {VOTE_OPTIONS.map(({ key, label, emoji, activeColor }) => {
          const isActive = myVote === key
          return (
            <button
              key={key}
              onClick={() => handleVote(key)}
              disabled={voting}
              style={{
                flex: 1,
                padding: '8px 4px',
                borderRadius: '10px',
                border: isActive ? `2px solid ${activeColor}` : '2px solid #E5E5EA',
                background: isActive ? `${activeColor}18` : '#F2F2F7',
                cursor: voting ? 'default' : 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '2px',
                opacity: voting && !isActive ? 0.5 : 1,
                transition: 'all 0.15s',
              }}
            >
              <span style={{ fontSize: '16px' }}>{emoji}</span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: isActive ? '700' : '500',
                  color: isActive ? activeColor : '#8E8E93',
                }}
              >
                {label}
              </span>
              {totalVotes > 0 && (
                <span style={{ fontSize: '11px', fontWeight: '600', color: isActive ? activeColor : '#C7C7CC' }}>
                  {tally[key]}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Booking link */}
      {proposal.bookingSearchUrl && (
        <a
          href={proposal.bookingSearchUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'block',
            textAlign: 'center',
            padding: '10px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg,#5856D6,#007AFF)',
            color: '#fff',
            fontSize: '13px',
            fontWeight: '600',
            textDecoration: 'none',
          }}
        >
          Search Flights ✈️
        </a>
      )}
    </div>
  )
}

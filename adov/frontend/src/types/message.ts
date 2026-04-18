// TypeScript interfaces for all message and wish pool data shapes exchanged with the backend.

export type MessageType = 'user' | 'ai' | 'wishpool_confirm' | 'vote' | 'proposal' | 'reset'

export interface ParsedData {
  destination: string
  tags: string[]
  estimatedCost?: 'budget' | 'mid-range' | 'luxury'
  confidence: number
}

export interface ProposalData {
  proposalId: string
  destination: string
  suggestedDates: { start: string; end: string }
  estimatedCostPerPerson: number
  flightEstimate?: number | null
  rationale: string
  tradeoff: string
  bookingSearchUrl?: string
  votes?: Record<string, 'yes' | 'no' | 'maybe'>
}

export interface Message {
  id: string
  type: MessageType
  senderId: string
  senderName?: string
  text: string
  timestamp?: string
  attachedUrl?: string
  parsedData?: ParsedData
  proposalsData?: ProposalData[]
}

// TypeScript interfaces for all message and wish pool data shapes exchanged with the backend.

export type MessageType = 'user' | 'ai' | 'wishpool_confirm' | 'vote' | 'proposal' | 'reset'

export interface ImageAnalysis {
  processor: 'local_ocr' | 'openai_vision'
  contentCategory: 'travel_related' | 'non_travel_text' | 'non_travel_image' | 'unknown'
  summary?: string
  extractedText?: string
  confidence?: number
  qualityScore?: number
  travelSignals?: Record<string, { value: string; confidence: number | null }[]>
  error?: string
}

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
  imageUrl?: string   // local blob URL only — never returned by backend, used for optimistic preview
  imageMimeType?: string
  imageName?: string
  analysisStatus?: 'pending' | 'completed' | 'failed'
  imageAnalysis?: ImageAnalysis
  analysisReplyMessageId?: string
}

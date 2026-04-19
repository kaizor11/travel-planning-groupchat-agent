// TypeScript interfaces for all message and wish pool data shapes exchanged with the backend.

export type MessageType = 'user' | 'ai' | 'wishpool_confirm' | 'vote' | 'proposal' | 'reset'
export type AnalysisStatus = 'pending' | 'completed' | 'failed'
export type Processor = 'local_ocr' | 'openai_vision'

export interface ParsedData {
  destination: string
  tags: string[]
  estimatedCost?: 'budget' | 'mid-range' | 'luxury'
  confidence: number
}

export interface SignalItem {
  value: string
  confidence: number | null
}

export interface TravelSignals {
  locations: SignalItem[]
  dates: SignalItem[]
  prices: SignalItem[]
  lodging: SignalItem[]
  transport: SignalItem[]
  bookingSignals: SignalItem[]
}

export interface ImageAnalysis {
  processor: Processor
  summary: string | null
  extractedText: string | null
  confidence: number | null
  qualityScore: number | null
  travelSignals: TravelSignals
  error: string | null
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
  imageUrl?: string
  imagePath?: string
  imageMimeType?: string
  imageName?: string
  analysisStatus?: AnalysisStatus
  imageAnalysis?: ImageAnalysis | null
  analysisReplyMessageId?: string | null
  replyToMessageId?: string
  updatedAt?: string
}

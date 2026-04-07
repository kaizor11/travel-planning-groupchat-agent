// TypeScript interfaces for all message and wish pool data shapes exchanged with the backend.

export type MessageType = 'user' | 'ai' | 'wishpool_confirm' | 'vote' | 'proposal'

export interface ParsedData {
  destination: string
  tags: string[]
  estimatedCost?: 'budget' | 'mid-range' | 'luxury'
  confidence: number
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
}

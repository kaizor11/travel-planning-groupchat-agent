// Top-level router: redirects / to the default trip and maps /trips/:tripId to ChatPage.
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ChatPage from './pages/ChatPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/trips/test-trip-123" replace />} />
        <Route path="/trips/:tripId" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  )
}

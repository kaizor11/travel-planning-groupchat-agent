// Top-level router: auth guard wraps protected routes; unauthenticated users go to /login.
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import JoinTripPage from './pages/JoinTripPage'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100dvh',
          background: '#F2F2F7',
        }}
      >
        <div style={{ fontSize: '32px' }}>✈️</div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/join/:tripId" element={<JoinTripPage />} />
        <Route
          path="/"
          element={
            <AuthGuard>
              <Navigate to="/trips/test-trip-123" replace />
            </AuthGuard>
          }
        />
        <Route
          path="/trips/:tripId"
          element={
            <AuthGuard>
              <ChatPage />
            </AuthGuard>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

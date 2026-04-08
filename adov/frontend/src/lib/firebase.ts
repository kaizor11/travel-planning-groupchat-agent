// Firebase client initialization: auth instance and Google provider with Calendar scope.
import { initializeApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

const app = initializeApp(firebaseConfig)

export const auth = getAuth(app)

export const googleProvider = new GoogleAuthProvider()
// Request read-only calendar access during sign-in
googleProvider.addScope('https://www.googleapis.com/auth/calendar.readonly')
// Always prompt account chooser so multi-account dev is easy
googleProvider.setCustomParameters({ prompt: 'select_account' })

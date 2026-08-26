import { initializeApp, getApps, getApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider, signInWithPopup } from 'firebase/auth'

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || 'AIzaSyBzp9q544ynge1v0wnVpv2bf0ZYNGddsuM',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || 'synthai-learn.firebaseapp.com',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'synthai-learn',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '1:668644380962:web:6ce9052bc7515a3fecd57b',
}

export function getClientAuth() {
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig)
  return getAuth(app)
}

export async function signInWithGoogle(): Promise<{ idToken: string; email?: string; displayName?: string }> {
  const auth = getClientAuth()
  const provider = new GoogleAuthProvider()
  provider.setCustomParameters({ prompt: 'select_account' })
  const result = await signInWithPopup(auth, provider)
  const idToken = await result.user.getIdToken()
  return {
    idToken,
    email: result.user.email ?? undefined,
    displayName: result.user.displayName ?? undefined,
  }
}

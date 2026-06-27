import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
} from "firebase/auth";

import { getCurrentUser } from "../api/client";
import { firebaseAuth, googleAuthProvider } from "../firebase";
import type { AuthenticatedUser } from "../types/api";

interface AuthContextValue {
  user: AuthenticatedUser | null;
  loading: boolean;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  getIdToken: () => Promise<string>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Authentication failed";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(
    () =>
      onAuthStateChanged(firebaseAuth, async (firebaseUser) => {
        setLoading(true);
        setError(null);

        if (!firebaseUser) {
          setUser(null);
          setLoading(false);
          return;
        }

        try {
          const idToken = await firebaseUser.getIdToken();
          setUser(await getCurrentUser(idToken));
        } catch (authError) {
          setUser(null);
          setError(errorMessage(authError));
          await firebaseSignOut(firebaseAuth);
        } finally {
          setLoading(false);
        }
      }),
    [],
  );

  const signInWithGoogle = useCallback(async () => {
    setError(null);
    try {
      await signInWithPopup(firebaseAuth, googleAuthProvider);
    } catch (authError) {
      setError(errorMessage(authError));
    }
  }, []);

  const signOut = useCallback(async () => {
    setError(null);
    await firebaseSignOut(firebaseAuth);
  }, []);

  const getIdToken = useCallback(async () => {
    const firebaseUser = firebaseAuth.currentUser;
    if (!firebaseUser) {
      throw new Error("Sign in to continue");
    }
    return firebaseUser.getIdToken();
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      signInWithGoogle,
      signOut,
      getIdToken,
    }),
    [user, loading, error, signInWithGoogle, signOut, getIdToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

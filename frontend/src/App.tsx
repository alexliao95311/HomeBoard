import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";

import { getHealth } from "./api/client";
import { useAuth } from "./context/AuthContext";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { DocumentTextPage } from "./pages/DocumentTextPage";

type BackendStatus = "checking" | "ok" | "offline";

function App() {
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");
  const {
    user,
    loading: authLoading,
    error: authError,
    signInWithGoogle,
    signOut,
  } = useAuth();

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => setBackendStatus(health.status))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setBackendStatus("offline");
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to="/" aria-label="HOA AI Assistant dashboard">
          <span className="brand__mark">H</span>
          <span>HOA AI Assistant</span>
        </Link>
        <div className="header-actions">
          {user ? (
            <nav className="site-nav" aria-label="Primary navigation">
              <NavLink to="/" end>
                Dashboard
              </NavLink>
              <NavLink to="/documents">Documents</NavLink>
            </nav>
          ) : null}
          <div className={`api-status api-status--${backendStatus}`}>
            <span className="api-status__dot" />
            Backend {backendStatus}
          </div>
          {authLoading ? (
            <span className="auth-loading">Checking account…</span>
          ) : user ? (
            <div className="account">
              {user.picture ? (
                <img
                  className="account__avatar"
                  src={user.picture}
                  alt=""
                  referrerPolicy="no-referrer"
                />
              ) : null}
              <span className="account__name">
                {user.name ?? user.email ?? "Signed in"}
              </span>
              <button
                className="auth-button auth-button--quiet"
                type="button"
                onClick={() => void signOut()}
              >
                Sign out
              </button>
            </div>
          ) : (
            <button
              className="auth-button"
              type="button"
              onClick={() => void signInWithGoogle()}
            >
              <span aria-hidden="true">G</span>
              Sign in with Google
            </button>
          )}
        </div>
      </header>

      {authError ? (
        <div className="auth-error" role="alert">
          {authError}
        </div>
      ) : null}

      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:documentId" element={<DocumentTextPage />} />
      </Routes>

      <footer>
        <span>HOA AI Assistant</span>
        <span>Human review required for all AI-generated conclusions.</span>
      </footer>
    </div>
  );
}

export default App;

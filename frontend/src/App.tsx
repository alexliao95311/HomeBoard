import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { getHealth } from "./api/client";
import { useAuth } from "./context/AuthContext";
import { ContractReviewPage } from "./pages/ContractReviewPage";
import { ContractsPage } from "./pages/ContractsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { DocumentTextPage } from "./pages/DocumentTextPage";
import { PrivacySecurityPage } from "./pages/PrivacySecurityPage";

type BackendStatus = "checking" | "ok" | "offline";

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [pathname]);

  return null;
}

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
      <ScrollToTop />
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
              <NavLink to="/contracts">Contracts</NavLink>
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
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/contracts/:contractId/review" element={<ContractReviewPage />} />
        <Route path="/privacy-security" element={<PrivacySecurityPage />} />
      </Routes>

      <footer>
        <span>HOA AI Assistant</span>
        <div className="footer-meta">
          <span>Human review required for all AI-generated conclusions.</span>
          <Link to="/privacy-security">Privacy &amp; security</Link>
        </div>
      </footer>
    </div>
  );
}

export default App;

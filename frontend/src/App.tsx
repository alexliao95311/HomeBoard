import { useEffect, useState } from "react";

import { getHealth } from "./api/client";
import { FeatureCard } from "./components/FeatureCard";
import { useAuth } from "./context/AuthContext";

type BackendStatus = "checking" | "ok" | "offline";

const features = [
  {
    icon: "DOC",
    title: "Document workspace",
    description:
      "Organize contracts, statements, budgets, invoices, and reserve studies.",
    phase: "Phase 2",
  },
  {
    icon: "CTR",
    title: "Contract review",
    description:
      "Extract key terms, flag risk, score proposals, and compare vendors.",
    phase: "Phase 3",
  },
  {
    icon: "FIN",
    title: "Financial oversight",
    description:
      "Track budget variance, categorize transactions, and surface anomalies.",
    phase: "Phase 4",
  },
  {
    icon: "RPT",
    title: "Board-ready reports",
    description:
      "Turn reviewed information into clear memos, summaries, and action items.",
    phase: "Phase 5",
  },
];

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
        <a className="brand" href="/" aria-label="HOA AI Assistant home">
          <span className="brand__mark">H</span>
          <span>HOA AI Assistant</span>
        </a>
        <div className="header-actions">
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

      <main>
        <section className="hero">
          <p className="eyebrow">Clarity for every board decision</p>
          <h1>Contracts and finances, reviewed with confidence.</h1>
          <p className="hero__copy">
            A secure workspace for HOA boards to understand vendor agreements,
            monitor financial activity, and prepare better meetings.
          </p>
          <div className="hero__actions">
            {user ? (
              <a className="button button--primary" href="#workspace">
                Explore the workspace
              </a>
            ) : (
              <button
                className="button button--primary"
                type="button"
                onClick={() => void signInWithGoogle()}
              >
                Continue with Google
              </button>
            )}
            <a
              className="button button--secondary"
              href="http://localhost:8000/docs"
            >
              View API docs
            </a>
          </div>
          <p className="disclaimer">
            AI-assisted review supports—not replaces—legal, accounting, and
            board judgment.
          </p>
        </section>

        <section className="workspace" id="workspace">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Product foundation</p>
              <h2>One place for the board&apos;s essential work</h2>
            </div>
            <p>
              The initial shell is ready. Each module will be delivered in
              small, testable phases.
            </p>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <FeatureCard key={feature.title} {...feature} />
            ))}
          </div>
        </section>
      </main>

      <footer>
        <span>HOA AI Assistant</span>
        <span>Human review required for all AI-generated conclusions.</span>
      </footer>
    </div>
  );
}

export default App;

import { Link } from "react-router-dom";

import { FeatureCard } from "../components/FeatureCard";
import { useAuth } from "../context/AuthContext";

const features = [
  {
    icon: "DOC",
    title: "Document workspace",
    description:
      "Organize contracts, statements, budgets, invoices, and reserve studies.",
    phase: "Active",
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

export function DashboardPage() {
  const { user, signInWithGoogle } = useAuth();

  return (
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
            <>
              <Link className="button button--primary" to="/documents">
                Open documents
              </Link>
              <Link className="button button--secondary" to="/contracts">
                Review contracts
              </Link>
            </>
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
          AI-assisted review supports—not replaces—legal, accounting, and board
          judgment.
        </p>
      </section>

      <section className="workspace" id="workspace">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Product foundation</p>
            <h2>One place for the board&apos;s essential work</h2>
          </div>
          <p>
            Upload and organize documents now. Additional review modules will
            be delivered in small, testable phases.
          </p>
        </div>
        <div className="feature-grid">
          {features.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </div>
      </section>
    </main>
  );
}

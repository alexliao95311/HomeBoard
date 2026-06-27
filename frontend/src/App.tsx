import { useEffect, useState } from "react";

import { getHealth } from "./api/client";
import { FeatureCard } from "./components/FeatureCard";

type ApiState = "checking" | "connected" | "offline";

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
  const [apiState, setApiState] = useState<ApiState>("checking");

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then(() => setApiState("connected"))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setApiState("offline");
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
        <div className={`api-status api-status--${apiState}`}>
          <span className="api-status__dot" />
          API {apiState}
        </div>
      </header>

      <main>
        <section className="hero">
          <p className="eyebrow">Clarity for every board decision</p>
          <h1>Contracts and finances, reviewed with confidence.</h1>
          <p className="hero__copy">
            A secure workspace for HOA boards to understand vendor agreements,
            monitor financial activity, and prepare better meetings.
          </p>
          <div className="hero__actions">
            <a className="button button--primary" href="#workspace">
              Explore the workspace
            </a>
            <a
              className="button button--secondary"
              href="http://localhost:5000/docs"
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

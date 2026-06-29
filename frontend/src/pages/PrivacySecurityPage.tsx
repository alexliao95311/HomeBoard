const securityPractices = [
  {
    label: "Identity",
    title: "Google sign-in through Firebase",
    copy: "Authentication is handled by Firebase. The app verifies short-lived Firebase ID tokens on protected backend requests and does not store Google passwords.",
  },
  {
    label: "Access",
    title: "Organization-level separation",
    copy: "Documents and contract data are scoped to the signed-in user's organization. The backend checks that scope before returning or processing protected records.",
  },
  {
    label: "Files",
    title: "Defensive document handling",
    copy: "Uploads are restricted to approved file types and 25 MB. Filenames are sanitized, every file receives a SHA-256 fingerprint, and document actions require authentication.",
  },
  {
    label: "Secrets",
    title: "Credentials stay server-side",
    copy: "Firebase Admin credentials are mounted into the backend and are never sent to the browser. Environment files and service-account keys are excluded from source control.",
  },
  {
    label: "Data",
    title: "Constrained database access",
    copy: "PostgreSQL foreign keys preserve organization and document relationships. Schema changes are versioned with Alembic, and uploads create an audit event.",
  },
  {
    label: "Review",
    title: "Humans remain in control",
    copy: "AI-generated summaries and risk assessments are advisory. The product clearly requires human review before legal, financial, or board decisions.",
  },
];

const privacyItems = [
  {
    title: "Account information",
    copy: "We use the name, email address, profile image, and Firebase user identifier supplied during Google sign-in to identify your account.",
  },
  {
    title: "HOA documents",
    copy: "Files you upload, their metadata, extracted text, and generated review results are used only to provide the document and contract-review features.",
  },
  {
    title: "Operational records",
    copy: "The application records limited activity metadata, such as upload audit events, to support traceability and troubleshooting.",
  },
];

export function PrivacySecurityPage() {
  return (
    <main className="trust-page">
      <section className="trust-hero" aria-labelledby="trust-title">
        <p className="eyebrow">Privacy &amp; security</p>
        <h1 id="trust-title">HOA records deserve careful handling.</h1>
        <p className="trust-hero__copy">
          Security is built in layers: trusted authentication, organization
          boundaries, defensive file handling, protected credentials, and
          human oversight. Here is a plain-language account of what the
          application protects and how.
        </p>
        <div className="trust-summary" role="list" aria-label="Security summary">
          <span role="listitem">Firebase authentication</span>
          <span role="listitem">Organization-scoped access</span>
          <span role="listitem">Audited uploads</span>
        </div>
      </section>

      <section className="trust-section" aria-labelledby="protections-title">
        <div className="trust-section__heading">
          <div>
            <p className="eyebrow">Current safeguards</p>
            <h2 id="protections-title">Protection at every boundary.</h2>
          </div>
          <p>
            Sensitive checks live in the backend, where they cannot be bypassed
            by changing browser code.
          </p>
        </div>

        <div className="security-grid">
          {securityPractices.map((practice) => (
            <article className="security-card" key={practice.label}>
              <span className="security-card__label">{practice.label}</span>
              <h3>{practice.title}</h3>
              <p>{practice.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="privacy-section" aria-labelledby="privacy-title">
        <div className="privacy-section__intro">
          <p className="eyebrow">Your information</p>
          <h2 id="privacy-title">What the application handles.</h2>
          <p>
            The app is designed to collect only the information needed to
            identify users, organize HOA work, and provide requested analysis.
          </p>
        </div>

        <div className="privacy-list">
          {privacyItems.map((item, index) => (
            <article className="privacy-item" key={item.title}>
              <span aria-hidden="true">0{index + 1}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.copy}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="security-note" aria-labelledby="storage-title">
        <div>
          <p className="eyebrow">Clear about the current stage</p>
          <h2 id="storage-title">Local development is not production.</h2>
        </div>
        <div>
          <p>
            The current document service stores uploaded files on the backend's
            local storage volume. Firebase Cloud Storage is planned but is not
            yet connected to uploads.
          </p>
          <p>
            A production deployment should use HTTPS through Caddy, encrypted
            managed storage, restricted infrastructure access, tested backups,
            key rotation, monitoring, and a formal retention and deletion
            policy.
          </p>
        </div>
      </section>

      <p className="policy-note">
        This page describes the application's current technical design. It is
        not a substitute for a formal privacy policy, security audit, or legal
        review before production use.
      </p>
    </main>
  );
}

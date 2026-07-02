import { useEffect, useState } from "react";
import { getUserSettings, updateUserSettings } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { AI_MODELS } from "../types/api";

export function SettingsPage() {
  const { user, getIdToken } = useAuth();
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveLabel, setSaveLabel] = useState("Save");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void (async () => {
      try {
        const token = await getIdToken();
        const settings = await getUserSettings(token);
        if (!cancelled) setSelectedModel(settings.preferred_model);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load settings");
      }
    })();
    return () => { cancelled = true; };
  }, [user, getIdToken]);

  async function handleSave() {
    if (!selectedModel) return;
    setSaving(true);
    setError(null);
    try {
      const token = await getIdToken();
      await updateUserSettings(token, { preferred_model: selectedModel });
      setSaveLabel("Saved!");
      setTimeout(() => setSaveLabel("Save"), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  }

  if (!user) {
    return (
      <main className="settings-page">
        <p className="empty-state">Sign in to manage your settings.</p>
      </main>
    );
  }

  return (
    <main className="settings-page">
      <div className="settings-page__inner">
        <p className="eyebrow">Account settings</p>
        <h1 className="page-title">Settings</h1>

        <section className="settings-section">
          <h2 className="settings-section__title">AI model</h2>
          <p className="settings-section__desc">
            Choose the model used for contract reviews and comparisons.
          </p>
          <div className="model-grid">
            {AI_MODELS.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`model-card${selectedModel === m.id ? " model-card--selected" : ""}`}
                onClick={() => setSelectedModel(m.id)}
                disabled={selectedModel === null}
              >
                <span className="model-card__provider">{m.provider}</span>
                <span className="model-card__label">{m.label}</span>
              </button>
            ))}
          </div>

          {error ? (
            <div className="document-error" role="alert" style={{ marginTop: 16 }}>
              {error}
            </div>
          ) : null}

          <div style={{ marginTop: 24 }}>
            <button
              type="button"
              className="button button--primary"
              onClick={() => void handleSave()}
              disabled={saving || selectedModel === null}
            >
              {saving ? "Saving…" : saveLabel}
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}

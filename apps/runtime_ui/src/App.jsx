import { startTransition, useEffect, useState } from "react";

const runtimeSummaryUrl = "/api/runtime/ui/v1/summary";

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value);
}

function buildDatasetDetail(item) {
  const parts = [item.connector, item.semantic_model].filter(Boolean);
  return parts.length > 0 ? parts.join(" | ") : "No connector metadata";
}

function buildConnectorDetail(item) {
  const parts = [item.connector_type, item.supports_sync ? "sync enabled" : "query only"].filter(Boolean);
  return parts.join(" | ");
}

function App() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadSummary() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(runtimeSummaryUrl, {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Runtime UI request failed with status ${response.status}`);
      }

      const payload = await response.json();
      startTransition(() => {
        setSummary(payload);
      });
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Unable to load runtime summary.";
      startTransition(() => {
        setError(message);
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSummary();
  }, []);

  const runtime = summary?.runtime ?? {};
  const health = summary?.health ?? {};
  const counts = summary?.counts ?? {};
  const datasets = summary?.datasets ?? [];
  const connectors = summary?.connectors ?? [];
  const features = summary?.features ?? [];

  return (
    <main className="shell">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Langbridge Runtime</p>
          <h1>Portable runtime surface for operators and builders.</h1>
          <p className="lede">
            This UI stays runtime-owned. Source lives in <code>apps/runtime_ui</code>, the compiled bundle lands
            in <code>langbridge/ui/static</code>, and the runtime host serves it when the <code>ui</code> feature
            is enabled.
          </p>
        </div>
        <div className="hero-actions">
          <button className="refresh" type="button" onClick={loadSummary} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh runtime"}
          </button>
          <div className="hint">Endpoint: /api/runtime/ui/v1/summary</div>
        </div>
      </section>

      <section className="stats">
        <article className="stat-card">
          <span className="stat-label">Health</span>
          <strong>{formatValue(health.status || (error ? "error" : "loading"))}</strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">Datasets</span>
          <strong>{formatValue(counts.datasets ?? 0)}</strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">Connectors</span>
          <strong>{formatValue(counts.connectors ?? 0)}</strong>
        </article>
      </section>

      {error ? <section className="error-banner">{error}</section> : null}

      <section className="content-grid">
        <article className="panel spotlight">
          <div className="panel-header">
            <h2>Runtime identity</h2>
            <span className="chip">{formatValue(runtime.mode || "configured_local")}</span>
          </div>
          <dl className="meta-grid">
            <div>
              <dt>Workspace</dt>
              <dd>{formatValue(runtime.workspace_id)}</dd>
            </div>
            <div>
              <dt>Actor</dt>
              <dd>{formatValue(runtime.actor_id)}</dd>
            </div>
            <div>
              <dt>Default semantic model</dt>
              <dd>{formatValue(runtime.default_semantic_model)}</dd>
            </div>
            <div>
              <dt>Default agent</dt>
              <dd>{formatValue(runtime.default_agent)}</dd>
            </div>
            <div>
              <dt>Enabled features</dt>
              <dd>{features.length > 0 ? features.join(", ") : "none"}</dd>
            </div>
          </dl>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Datasets</h2>
            <span className="chip subtle">{datasets.length} visible</span>
          </div>
          <ul className="item-list">
            {datasets.length === 0 ? <li className="empty">No datasets are configured yet.</li> : null}
            {datasets.map((item) => (
              <li key={item.id || item.name}>
                <strong>{item.name}</strong>
                <span>{buildDatasetDetail(item)}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Connectors</h2>
            <span className="chip subtle">{connectors.length} visible</span>
          </div>
          <ul className="item-list">
            {connectors.length === 0 ? <li className="empty">No connectors are configured yet.</li> : null}
            {connectors.map((item) => (
              <li key={item.id || item.name}>
                <strong>{item.name}</strong>
                <span>{buildConnectorDetail(item)}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}

export default App;

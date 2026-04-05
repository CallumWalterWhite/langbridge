import { formatValue } from "../lib/format";
import {
  buildDiagnosticsHighlights,
  buildDiagnosticsNotes,
  deriveRuntimeResultState,
  hasRenderableVisualization,
  normalizeAnalystOutcome,
  normalizeTabularResult,
  normalizeVisualizationSpec,
  renderJson,
} from "../lib/runtimeUi";
import { ChartPreview } from "./ChartPreview";
import { ResultTable } from "./ResultTable";

function formatLabel(value) {
  return String(value || "")
    .replaceAll("-", " ")
    .replaceAll("_", " ")
    .trim();
}

function toTitleCase(value) {
  return formatLabel(value).replace(/\b\w/g, (match) => match.toUpperCase());
}

function buildSummaryFallback(state) {
  switch (state.kind) {
    case "empty_result":
      return "The request completed, but no rows matched the current scope.";
    case "needs_clarification":
      return "The runtime needs one more detail before it can continue.";
    case "invalid_request":
      return "The runtime could not act on the request as written.";
    case "query_error":
      return "The runtime could not turn this request into a valid query.";
    case "access_denied":
      return "The runtime blocked this request based on the current access policy.";
    case "execution_failure":
      return "The runtime could not complete this request.";
    case "success_chart":
      return "The runtime returned a structured answer with a visualization and supporting rows.";
    case "success_rows":
      return "The runtime returned structured rows for this request.";
    default:
      return "";
  }
}

function buildStatePills({ result, visualization, diagnostics }) {
  const normalizedResult = result ? normalizeTabularResult(result) : null;
  const normalizedVisualization = normalizeVisualizationSpec(visualization);
  const outcome = normalizeAnalystOutcome(diagnostics);
  const pills = [];

  if (normalizedResult?.rowCount !== undefined && normalizedResult?.rowCount !== null) {
    pills.push(`${Number(normalizedResult.rowCount).toLocaleString()} rows`);
  }
  if (normalizedVisualization?.chartType && normalizedVisualization.chartType !== "table") {
    pills.push(toTitleCase(normalizedVisualization.chartType));
  }
  if (outcome?.retryCount > 0) {
    pills.push(`${outcome.retryCount} retr${outcome.retryCount === 1 ? "y" : "ies"}`);
  }
  if (outcome?.selectedAssetName) {
    pills.push(outcome.selectedAssetName);
  }

  return pills;
}

export function RuntimeResultPanel({
  summary,
  result,
  visualization,
  diagnostics,
  status = "ready",
  errorMessage = "",
  errorStatus = null,
  maxPreviewRows = 12,
  diagnosticsLabel = "Execution diagnostics",
}) {
  const normalizedResult = result ? normalizeTabularResult(result) : null;
  const normalizedVisualization = normalizeVisualizationSpec(visualization);
  const state = deriveRuntimeResultState({
    status,
    result: normalizedResult,
    visualization: normalizedVisualization,
    diagnostics,
    errorMessage,
    errorStatus,
  });
  const summaryText = String(summary || "").trim() || buildSummaryFallback(state);
  const diagnosticsHighlights = buildDiagnosticsHighlights(diagnostics);
  const diagnosticsNotes = buildDiagnosticsNotes(diagnostics, normalizedVisualization);
  const statePills = buildStatePills({
    result: normalizedResult,
    visualization: normalizedVisualization,
    diagnostics,
  });
  const showChart =
    Boolean(normalizedResult) &&
    Boolean(normalizedVisualization) &&
    state.showChart &&
    hasRenderableVisualization(normalizedVisualization);
  const showTable =
    Boolean(normalizedResult) &&
    (state.showTable || normalizedVisualization?.chartType === "table");

  return (
    <div className="runtime-result-stack">
      <div className={`runtime-result-state runtime-result-state--${state.tone}`}>
        <div className="runtime-result-state-copy">
          <span className="runtime-result-state-label">{state.label}</span>
          <strong>{state.title}</strong>
          <p>{state.description}</p>
        </div>
        {statePills.length > 0 ? (
          <div className="runtime-result-state-pills">
            {statePills.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        ) : null}
      </div>

      {summaryText ? (
        <section className="runtime-result-section">
          <div className="runtime-result-section-head">
            <div>
              <h4>Answer</h4>
              <p>Summary returned by the runtime for this request.</p>
            </div>
          </div>
          <p className="assistant-summary-card">{summaryText}</p>
        </section>
      ) : null}

      {showChart ? (
        <section className="runtime-result-section">
          <div className="runtime-result-section-head">
            <div>
              <h4>Visualization</h4>
              <p>
                {normalizedVisualization?.subtitle ||
                  `${toTitleCase(normalizedVisualization?.chartType)} preview generated from the returned result.`}
              </p>
            </div>
          </div>
          <ChartPreview
            title={normalizedVisualization?.title}
            result={normalizedResult}
            metadata={Array.isArray(normalizedResult?.metadata) ? normalizedResult.metadata : []}
            visualization={normalizedVisualization}
            preferredDimension={normalizedVisualization?.x}
            preferredMeasure={normalizedVisualization?.y?.[0]}
          />
        </section>
      ) : null}

      {showTable ? (
        <section className="runtime-result-section">
          <div className="runtime-result-section-head">
            <div>
              <h4>Underlying rows</h4>
              <p>Preview the tabular result that backs the answer and chart.</p>
            </div>
            {normalizedResult?.duration_ms !== undefined && normalizedResult?.duration_ms !== null ? (
              <span className="runtime-result-section-meta">
                {formatValue(normalizedResult.duration_ms)} ms
              </span>
            ) : null}
          </div>
          <ResultTable result={normalizedResult} maxPreviewRows={maxPreviewRows} />
        </section>
      ) : null}

      {diagnostics && typeof diagnostics === "object" ? (
        <details className="diagnostics-disclosure">
          <summary>{diagnosticsLabel}</summary>
          {diagnosticsHighlights.length > 0 ? (
            <div className="diagnostics-highlight-grid">
              {diagnosticsHighlights.map((item) => (
                <div key={`${item.label}-${item.value}`} className="diagnostics-highlight-card">
                  <span>{item.label}</span>
                  <strong>{toTitleCase(item.value)}</strong>
                </div>
              ))}
            </div>
          ) : null}
          {diagnosticsNotes.length > 0 ? (
            <div className="diagnostics-note-list">
              {diagnosticsNotes.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </div>
          ) : null}
          <pre className="code-block compact">{renderJson(diagnostics)}</pre>
        </details>
      ) : null}
    </div>
  );
}

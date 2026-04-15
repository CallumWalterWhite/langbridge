import {
  Activity,
  Blocks,
  Bot,
  Cable,
  Database,
  MessageSquareText,
  Table2,
} from "lucide-react";
import { Link } from "react-router-dom";

import { MetricCard, FeatureCard, PageEmpty } from "../components/PagePrimitives";
import { useAsyncData } from "../hooks/useAsyncData";
import { readStoredJson } from "../hooks/usePersistentState";
import {
  fetchAgents,
  fetchConnectors,
  fetchDatasets,
  fetchRuntimeSummary,
  fetchSemanticModels,
  fetchThreads,
} from "../lib/runtimeApi";
import {
  DASHBOARD_BUILDER_STORAGE_KEY,
  SQL_HISTORY_STORAGE_KEY,
  SQL_SAVED_STORAGE_KEY,
  buildActivityFeed,
  formatRelativeTime,
} from "../lib/runtimeUi";
import { formatValue, getRuntimeTimestamp } from "../lib/format";
import { ActivityPanel, QuickActionPanel } from "../components/overview/CommandCenterPanels";

function trimText(value, maxLength = 96) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 1)).trimEnd()}...`;
}

function buildThreadTitle(thread) {
  return thread?.title?.trim() || `Thread ${String(thread?.id || "").slice(0, 8)}`;
}

function buildQueryModeLabel(queryScope, connectionName = "") {
  if (queryScope === "semantic") {
    return "Semantic query";
  }
  if (queryScope === "source") {
    return connectionName ? `Source SQL on ${connectionName}` : "Source SQL";
  }
  return "Dataset SQL";
}

function sortByTimestampDesc(items) {
  return [...items].sort((left, right) => {
    const leftTime = getRuntimeTimestamp(left.timestamp || 0);
    const rightTime = getRuntimeTimestamp(right.timestamp || 0);
    return rightTime - leftTime;
  });
}

async function loadOverviewData() {
  const [summary, connectors, datasets, models, agents, threads] = await Promise.all([
    fetchRuntimeSummary(),
    fetchConnectors(),
    fetchDatasets(),
    fetchSemanticModels(),
    fetchAgents(),
    fetchThreads(),
  ]);

  return {
    summary: summary || {},
    connectors: Array.isArray(connectors?.items) ? connectors.items : [],
    datasets: Array.isArray(datasets?.items) ? datasets.items : [],
    models: Array.isArray(models?.items) ? models.items : [],
    agents: Array.isArray(agents?.items) ? agents.items : [],
    threads: Array.isArray(threads?.items) ? threads.items : [],
  };
}

export function OverviewPage() {
  const { data, loading, error, reload } = useAsyncData(loadOverviewData);
  const summary = data?.summary || {};
  const counts = summary.counts || {};
  const connectors = data?.connectors || [];
  const datasets = data?.datasets || [];
  const models = data?.models || [];
  const agents = data?.agents || [];
  const threads = data?.threads || [];
  const sortedThreads = sortByTimestampDesc(
    threads.map((thread) => ({
      ...thread,
      timestamp: thread.updated_at || thread.created_at,
    })),
  );
  const latestThread = sortedThreads[0] || null;
  const storedSqlHistory = readStoredJson(SQL_HISTORY_STORAGE_KEY, []);
  const sqlHistory = Array.isArray(storedSqlHistory) ? storedSqlHistory : [];
  const storedSavedQueries = readStoredJson(SQL_SAVED_STORAGE_KEY, []);
  const savedQueries = Array.isArray(storedSavedQueries) ? storedSavedQueries : [];
  const dashboardState = readStoredJson(DASHBOARD_BUILDER_STORAGE_KEY, { boards: [] });
  const boards = Array.isArray(dashboardState?.boards) ? dashboardState.boards : [];

  const activityItems = buildActivityFeed({ connectors, datasets, models, agents, threads });
  const recentExecutionItems = sortByTimestampDesc([
    ...sortedThreads.slice(0, 3).map((thread) => ({
      id: `thread-${thread.id}`,
      href: `/chat/${encodeURIComponent(String(thread.id))}`,
      title: buildThreadTitle(thread),
      kind: "Thread",
      description: "Continue an existing analytical thread.",
      timestamp: thread.updated_at || thread.created_at,
    })),
    ...sqlHistory.slice(0, 3).map((entry) => ({
      id: `query-${entry.id || entry.createdAt}`,
      href: "/query-workspace",
      title: buildQueryModeLabel(entry.queryScope, entry.connectionName),
      kind: "Query run",
      description: trimText(entry.query, 110) || "Open Query Workspace to continue this run.",
      timestamp: entry.createdAt,
    })),
    ...boards
      .filter((board) => board?.lastRefreshedAt)
      .slice(0, 2)
      .map((board) => ({
        id: `dashboard-${board.id}`,
        href: "/dashboards",
        title: board.name || "Runtime dashboard",
        kind: "Dashboard",
        description: "Local semantic dashboard refreshed against the runtime.",
        timestamp: board.lastRefreshedAt,
      })),
  ]).slice(0, 8);

  const quickActions = [
    {
      to: latestThread ? `/chat/${encodeURIComponent(String(latestThread.id))}` : "/chat",
      label: latestThread ? "Continue analysis" : "Ask the runtime",
      description: latestThread
        ? `Resume ${buildThreadTitle(latestThread)} and keep the investigation moving.`
        : "Start a question-first runtime thread with an execution agent.",
      icon: MessageSquareText,
      emphasis: "primary",
    },
    {
      to: "/runs",
      label: "Inspect recent runs",
      description: "Review thread turns, query executions, and dashboard widget runs in one place.",
      icon: Activity,
    },
    {
      to: "/query-workspace",
      label: "Open Query Workspace",
      description: "Use semantic querying first, with dataset and source SQL available when needed.",
      icon: Table2,
    },
    {
      to: "/semantic-models",
      label: "Shape semantic models",
      description: "Keep the semantic layer central to how the runtime answers questions.",
      icon: Blocks,
    },
    {
      to: "/datasets",
      label: "Review datasets",
      description: "Inspect dataset bindings, previews, and runtime execution resources.",
      icon: Database,
    },
    {
      to: "/connectors",
      label: "Inspect connectors",
      description: "Check source posture, sync scope, and runtime ingress state.",
      icon: Cable,
    },
  ];

  return (
    <div className="page-stack command-center-shell">
      <section className="surface-panel product-command-bar">
        <div className="product-command-bar-main">
          <div className="product-command-bar-copy">
            <p className="eyebrow">Command Center</p>
            <h2>Runtime that answers questions over data</h2>
            <div className="product-command-bar-meta">
              <span className="chip">{formatValue(counts.connectors ?? connectors.length)} connectors</span>
              <span className="chip">{formatValue(counts.datasets ?? datasets.length)} datasets</span>
              <span className="chip">{formatValue(counts.semantic_models ?? models.length)} models</span>
              <span className="chip">{formatValue(counts.threads ?? threads.length)} threads</span>
              <span className="chip">{summary.auth?.auth_enabled ? "Session scoped" : "Direct access"}</span>
            </div>
          </div>
          <div className="product-command-bar-actions">
            <Link className="primary-button" to="/chat">
              Ask runtime
            </Link>
            <Link className="ghost-button" to="/runs">
              View runs
            </Link>
            <button className="ghost-button" type="button" onClick={reload} disabled={loading}>
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>
      </section>

      <section className="metric-grid metric-grid--compact">
        <MetricCard
          icon={MessageSquareText}
          label="Active threads"
          value={formatValue(threads.length)}
          detail={
            latestThread
              ? `Latest activity ${formatRelativeTime(latestThread.updated_at || latestThread.created_at)}`
              : "No active threads yet"
          }
        />
        <MetricCard
          icon={Table2}
          label="Local query runs"
          value={formatValue(sqlHistory.length)}
          detail="Recent Query Workspace executions stored in this browser."
        />
        <MetricCard
          icon={Blocks}
          label="Semantic models"
          value={formatValue(models.length)}
          detail="Governed analytical layer available to ask flows and the query workspace."
        />
        <MetricCard
          icon={Bot}
          label="Runtime agents"
          value={formatValue(agents.length)}
          detail={summary.runtime?.default_agent ? `Default: ${summary.runtime.default_agent}` : "No default agent exposed"}
        />
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="command-center-grid">
        <section className="surface-panel command-primary-panel">
          <div className="command-panel-head-row">
            <div>
              <p className="command-panel-eyebrow">Primary workflows</p>
              <h3>Move from question to execution</h3>
            </div>
          </div>
          <QuickActionPanel actions={quickActions} />
        </section>

        <section className="surface-panel command-activity-panel">
          <div className="command-panel-heading">
            <div>
              <p className="command-panel-eyebrow">Operational signals</p>
              <h3>Runtime posture</h3>
            </div>
          </div>
          <div className="command-memory-list">
            <article className="command-memory-card">
              <span>Default agent</span>
              <strong>{summary.runtime?.default_agent || "No default agent"}</strong>
              <p>The default execution context exposed by this runtime.</p>
            </article>
            <article className="command-memory-card">
              <span>Default semantic model</span>
              <strong>{summary.runtime?.default_semantic_model || "No default model"}</strong>
              <p>The semantic layer most ready for governed analytical questions.</p>
            </article>
            <article className="command-memory-card">
              <span>Saved queries</span>
              <strong>{formatValue(savedQueries.length)}</strong>
              <p>Local query workspace snippets kept in this browser.</p>
            </article>
            <article className="command-memory-card">
              <span>Dashboard drafts</span>
              <strong>{formatValue(boards.length)}</strong>
              <p>Runtime-local dashboard work remains available without driving the main story.</p>
            </article>
          </div>
        </section>
      </section>

      <section className="command-center-grid secondary">
        <ActivityPanel
          title="Recent activity"
          eyebrow="Runtime resources"
          items={activityItems}
          emptyTitle="No recent activity"
          emptyMessage="Connectors, datasets, models, agents, and threads will appear here as the runtime fills out."
        />
        <ActivityPanel
          title="Recent threads and runs"
          eyebrow="Execution"
          items={recentExecutionItems}
          emptyTitle="No recent execution"
          emptyMessage="Ask flows, query runs, and dashboard refreshes will appear here once the runtime is in use."
        />
      </section>

      <section className="surface-panel command-activity-panel">
        <div className="command-panel-heading">
          <div>
            <p className="command-panel-eyebrow">Build layer</p>
            <h3>Shape the runtime resources that answer questions</h3>
          </div>
        </div>
        <div className="feature-grid">
          <FeatureCard
            to="/semantic-models"
            icon={Blocks}
            metric={`${formatValue(models.length)} models`}
            title="Semantic models"
            description="Keep the semantic layer central to how the runtime understands measures, dimensions, and governed analysis."
            cta="Open semantic models"
          />
          <FeatureCard
            to="/datasets"
            icon={Database}
            metric={`${formatValue(datasets.length)} datasets`}
            title="Datasets"
            description="Manage the runtime datasets that semantic models, ask flows, and query execution depend on."
            cta="Open datasets"
          />
          <FeatureCard
            to="/connectors"
            icon={Cable}
            metric={`${formatValue(connectors.length)} connectors`}
            title="Connectors"
            description="Control source connectivity, sync posture, and the runtime ingress layer."
            cta="Open connectors"
          />
        </div>
        <div className="callout command-secondary-callout">
          <strong>Dashboard Builder stays available</strong>
          <span>
            Dashboard Builder remains part of the runtime, but now sits behind the main ask, execution, and semantic-model story as a secondary build surface.
          </span>
          <Link className="ghost-button" to="/dashboards">
            Open Dashboard Builder
          </Link>
        </div>
      </section>

      {!loading &&
      connectors.length === 0 &&
      datasets.length === 0 &&
      models.length === 0 &&
      agents.length === 0 ? (
        <PageEmpty
          title="Runtime onboarding ready"
          message="The runtime is empty but healthy. Start with connectors, datasets, or semantic models to build the question-answering surface."
        />
      ) : null}
    </div>
  );
}

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Bot, Plus } from "lucide-react";

import { useAsyncData } from "../hooks/useAsyncData";
import {
  createThread,
  fetchAgents,
  fetchThreads,
} from "../lib/runtimeApi";
import { getErrorMessage, getRuntimeTimestamp } from "../lib/format";
import {
  CHAT_STARTERS,
  DEFAULT_CHAT_MESSAGE,
  formatRelativeTime,
} from "../lib/runtimeUi";

function buildPromptTitle(prompt) {
  const normalized = String(prompt || "")
    .trim()
    .replace(/\s+/g, " ");
  if (!normalized) {
    return undefined;
  }
  return normalized.slice(0, 80);
}

export function ChatIndexPage() {
  const navigate = useNavigate();
  const threadsState = useAsyncData(fetchThreads);
  const agentsState = useAsyncData(fetchAgents);
  const threads = Array.isArray(threadsState.data?.items) ? threadsState.data.items : [];
  const agents = Array.isArray(agentsState.data?.items) ? agentsState.data.items : [];
  const sortedThreads = [...threads].sort((left, right) => {
    const leftTime = getRuntimeTimestamp(left.updated_at || left.created_at || 0);
    const rightTime = getRuntimeTimestamp(right.updated_at || right.created_at || 0);
    return rightTime - leftTime;
  });
  const latestThread = sortedThreads[0] || null;
  const [selectedAgentName, setSelectedAgentName] = useState("");
  const [prompt, setPrompt] = useState(DEFAULT_CHAT_MESSAGE);
  const [asking, setAsking] = useState(false);
  const [creatingThread, setCreatingThread] = useState(false);
  const [mutationError, setMutationError] = useState("");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("runtime-ask-agent");
      if (stored) {
        setSelectedAgentName(stored);
      }
    } catch {}
  }, []);

  useEffect(() => {
    if (agents.length === 0) {
      return;
    }
    const hasSelectedAgent = agents.some((item) => item.name === selectedAgentName);
    if (!selectedAgentName || !hasSelectedAgent) {
      setSelectedAgentName(agents.find((item) => item.default)?.name || agents[0].name);
    }
  }, [agents, selectedAgentName]);

  useEffect(() => {
    try {
      if (selectedAgentName) {
        window.localStorage.setItem("runtime-ask-agent", selectedAgentName);
      }
    } catch {}
  }, [selectedAgentName]);

  async function handleAsk(event) {
    event.preventDefault();
    if (!selectedAgentName || !prompt.trim()) {
      return;
    }
    await handleCreateThread(prompt.trim(), buildPromptTitle(prompt));
  }

  async function handleCreateThread(seedMessage = "", title) {
    if (seedMessage) {
      setAsking(true);
    }
    setCreatingThread(true);
    setMutationError("");
    try {
      const createdThread = await createThread(title ? { title } : {});
      if (typeof window !== "undefined") {
        if (seedMessage) {
          window.sessionStorage.setItem(`runtime-thread-draft:${createdThread.id}`, seedMessage);
        }
        if (selectedAgentName) {
          window.localStorage.setItem(`runtime-thread-agent:${createdThread.id}`, selectedAgentName);
        }
      }
      navigate(`/chat/${createdThread.id}`);
      void threadsState.reload();
    } catch (caughtError) {
      setMutationError(getErrorMessage(caughtError));
    } finally {
      if (seedMessage) {
        setAsking(false);
      }
      setCreatingThread(false);
    }
  }

  return (
    <div className="chat-index-shell chat-home-shell chat-home-shell--minimal">
      <section className="chat-home-minimal-stage">
        {threadsState.error ? <div className="error-banner">{threadsState.error}</div> : null}
        {agentsState.error ? <div className="error-banner">{agentsState.error}</div> : null}
        {mutationError ? <div className="error-banner">{mutationError}</div> : null}

        <div className="chat-home-minimal-center">
          <div className="chat-home-copy chat-home-copy--minimal">
            <h2>What do you want to know?</h2>
            <p className="chat-home-copy-text">
              Ask the runtime a question and continue the conversation in a thread.
            </p>
          </div>

          <form className="chat-home-composer chat-home-composer--minimal" onSubmit={handleAsk}>
            <div className="chat-home-composer-top chat-home-composer-top--minimal">
              <label className="chat-home-agent-field chat-home-agent-field--minimal">
                <span>Agent</span>
                <select
                  className="select-input thread-agent-select"
                  value={selectedAgentName}
                  onChange={(event) => setSelectedAgentName(event.target.value)}
                  disabled={asking || agents.length === 0}
                >
                  {agents.map((item) => (
                    <option key={item.id || item.name} value={item.name}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>

              <div className="chat-home-toolbar-actions chat-home-toolbar-actions--minimal">
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => void handleCreateThread()}
                  disabled={creatingThread}
                >
                  <Plus className="button-icon" aria-hidden="true" />
                  {creatingThread ? "Creating..." : "Blank thread"}
                </button>
                <button className="ghost-button" type="button" onClick={() => navigate("/agents")}>
                  <Bot className="button-icon" aria-hidden="true" />
                  Agent library
                </button>
              </div>
            </div>

            <textarea
              className="textarea-input chat-home-textarea chat-home-textarea--minimal"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={5}
              disabled={asking}
              aria-label="Question"
              placeholder="Ask about your data, runtime activity, semantic models, or the next analytical step..."
            />

            <div className="chat-home-starters chat-home-starters--minimal">
              {CHAT_STARTERS.map((starter) => (
                <button
                  key={starter}
                  className="chat-home-starter"
                  type="button"
                  onClick={() => setPrompt(starter)}
                  disabled={asking}
                >
                  {starter}
                </button>
              ))}
            </div>

            <div className="chat-home-footer chat-home-footer--minimal">
              <p className="composer-note">
                {latestThread
                  ? `Latest thread updated ${formatRelativeTime(latestThread.updated_at || latestThread.created_at)}`
                  : "A new thread will be created when you send the first message."}
              </p>
              <div className="page-actions">
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => setPrompt(DEFAULT_CHAT_MESSAGE)}
                  disabled={asking}
                >
                  Load default
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={asking || !selectedAgentName || !prompt.trim()}
                >
                  <ArrowRight className="button-icon" aria-hidden="true" />
                  {asking ? "Asking runtime..." : "Ask runtime"}
                </button>
              </div>
            </div>
          </form>
        </div>
      </section>

      {sortedThreads.length > 0 ? (
        <section className="chat-home-history">
          <div className="chat-home-history-head">
            <h3>Recent</h3>
            {latestThread ? (
              <button
                className="ghost-button"
                type="button"
                onClick={() => navigate(`/chat/${latestThread.id}`)}
              >
                Continue latest
              </button>
            ) : null}
          </div>
          <div className="chat-home-history-strip">
            {sortedThreads.slice(0, 6).map((thread) => (
              <button
                key={thread.id}
                className="chat-home-history-item"
                type="button"
                onClick={() => navigate(`/chat/${thread.id}`)}
              >
                <strong>{thread.title || `Thread ${String(thread.id).slice(0, 8)}`}</strong>
                <span>
                  {thread.updated_at
                    ? `Updated ${formatRelativeTime(thread.updated_at)}`
                    : `Created ${formatRelativeTime(thread.created_at)}`}
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

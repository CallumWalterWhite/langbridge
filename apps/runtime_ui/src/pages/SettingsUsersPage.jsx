import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { KeyRound, ShieldCheck, ShieldOff, UserPlus, Users } from "lucide-react";

import { Panel, PageEmpty } from "../components/PagePrimitives";
import { SettingsSectionNav } from "../components/SettingsSectionNav";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, getErrorMessage } from "../lib/format";
import { createActor, fetchActors, resetActorPassword, updateActor } from "../lib/runtimeApi";
import { hasRuntimeAdminRole } from "../lib/runtimeAuthz";

const RUNTIME_ROLES = [
  { value: "admin", label: "Admin" },
  { value: "builder", label: "Builder" },
  { value: "analyst", label: "Analyst" },
  { value: "viewer", label: "Viewer" },
];

function buildCreateForm() {
  return {
    username: "",
    email: "",
    display_name: "",
    password: "",
    roles: ["viewer"],
  };
}

function buildPasswordForm() {
  return {
    password: "",
    must_rotate_password: false,
  };
}

function roleLabel(role) {
  return RUNTIME_ROLES.find((item) => item.value === role)?.label || role;
}

function actorStatusLabel(status) {
  return status === "disabled" ? "Disabled" : "Active";
}

function updateRoleList(list, role) {
  const items = Array.isArray(list) ? list : [];
  if (items.includes(role)) {
    const next = items.filter((item) => item !== role);
    return next.length > 0 ? next : items;
  }
  return [...items, role];
}

export function SettingsUsersPage({ authStatus, session }) {
  const isAdmin = hasRuntimeAdminRole(session?.roles);
  const { data, loading, error, reload, setData } = useAsyncData(fetchActors, [], {
    enabled: isAdmin,
    initialData: { items: [], total: 0 },
  });
  const actors = data?.items || [];
  const [selectedActorId, setSelectedActorId] = useState("");
  const [createForm, setCreateForm] = useState(buildCreateForm);
  const [accessForm, setAccessForm] = useState({ roles: ["viewer"], status: "active" });
  const [passwordForm, setPasswordForm] = useState(buildPasswordForm);
  const [createState, setCreateState] = useState({ submitting: false, error: "", success: "" });
  const [accessState, setAccessState] = useState({ submitting: false, error: "", success: "" });
  const [passwordState, setPasswordState] = useState({ submitting: false, error: "", success: "" });

  const selectedActor = useMemo(
    () => actors.find((actor) => actor.id === selectedActorId) || actors[0] || null,
    [actors, selectedActorId],
  );

  useEffect(() => {
    if (!selectedActor) {
      setSelectedActorId("");
      return;
    }
    if (!selectedActorId || !actors.some((actor) => actor.id === selectedActorId)) {
      setSelectedActorId(selectedActor.id);
    }
  }, [actors, selectedActor, selectedActorId]);

  useEffect(() => {
    if (!selectedActor) {
      setAccessForm({ roles: ["viewer"], status: "active" });
      setPasswordForm(buildPasswordForm());
      return;
    }
    setAccessForm({
      roles: Array.isArray(selectedActor.roles) && selectedActor.roles.length > 0 ? selectedActor.roles : ["viewer"],
      status: selectedActor.status || "active",
    });
    setPasswordForm(buildPasswordForm());
    setAccessState((current) => ({ ...current, error: "", success: "" }));
    setPasswordState((current) => ({ ...current, error: "", success: "" }));
  }, [selectedActor]);

  async function refreshActors({ focusActorId } = {}) {
    const payload = await reload();
    const nextActors = payload?.items || [];
    const nextFocusActorId =
      focusActorId && nextActors.some((actor) => actor.id === focusActorId)
        ? focusActorId
        : nextActors[0]?.id || "";
    setSelectedActorId(nextFocusActorId);
    return payload;
  }

  async function handleCreateActor(event) {
    event.preventDefault();
    setCreateState({ submitting: true, error: "", success: "" });
    try {
      const createdActor = await createActor(createForm);
      setCreateForm(buildCreateForm());
      setData((current) => {
        const items = [...(current?.items || []), createdActor];
        return { items, total: items.length };
      });
      setSelectedActorId(createdActor.id);
      setCreateState({
        submitting: false,
        error: "",
        success: `Created runtime user ${createdActor.username}.`,
      });
      await refreshActors({ focusActorId: createdActor.id });
    } catch (caughtError) {
      setCreateState({
        submitting: false,
        error: getErrorMessage(caughtError),
        success: "",
      });
    }
  }

  async function handleSaveAccess(event) {
    event.preventDefault();
    if (!selectedActor) {
      return;
    }
    setAccessState({ submitting: true, error: "", success: "" });
    try {
      const updatedActor = await updateActor(selectedActor.id, {
        roles: accessForm.roles,
        status: accessForm.status,
      });
      setData((current) => {
        const items = (current?.items || []).map((actor) =>
          actor.id === updatedActor.id ? updatedActor : actor,
        );
        return { items, total: items.length };
      });
      setAccessState({
        submitting: false,
        error: "",
        success: `Updated access for ${updatedActor.username}.`,
      });
      await refreshActors({ focusActorId: updatedActor.id });
    } catch (caughtError) {
      setAccessState({
        submitting: false,
        error: getErrorMessage(caughtError),
        success: "",
      });
    }
  }

  async function handleResetPassword(event) {
    event.preventDefault();
    if (!selectedActor) {
      return;
    }
    setPasswordState({ submitting: true, error: "", success: "" });
    try {
      const updatedActor = await resetActorPassword(selectedActor.id, passwordForm);
      setPasswordForm(buildPasswordForm());
      setData((current) => {
        const items = (current?.items || []).map((actor) =>
          actor.id === updatedActor.id ? updatedActor : actor,
        );
        return { items, total: items.length };
      });
      setPasswordState({
        submitting: false,
        error: "",
        success: `Reset password for ${updatedActor.username}.`,
      });
      await refreshActors({ focusActorId: updatedActor.id });
    } catch (caughtError) {
      setPasswordState({
        submitting: false,
        error: getErrorMessage(caughtError),
        success: "",
      });
    }
  }

  return (
    <div className="page-stack">
      <section className="surface-panel product-command-bar">
        <div className="product-command-bar-main">
          <div className="product-command-bar-copy">
            <p className="eyebrow">Governance</p>
            <h2>Runtime users</h2>
            <div className="product-command-bar-meta">
              <span className="chip">{authStatus?.auth_mode || "runtime auth"}</span>
              <span className="chip">Single workspace</span>
              <span className="chip">{actors.length} local users</span>
            </div>
          </div>
          <div className="product-command-bar-actions">
            <button className="ghost-button" type="button" onClick={() => void refreshActors()} disabled={loading || !isAdmin}>
              {loading ? "Refreshing..." : "Refresh users"}
            </button>
          </div>
        </div>
      </section>

      <SettingsSectionNav session={session} />

      {!isAdmin ? (
        <Panel title="Admin access required" className="compact-panel">
          <PageEmpty
            title="Runtime users are admin-managed"
            message="This session can use the runtime UI but cannot manage local runtime users."
            action={
              <Link className="ghost-link" to="/settings">
                Back to runtime settings
              </Link>
            }
          />
        </Panel>
      ) : (
        <>
          <section className="summary-grid">
            <article className="detail-card">
              <div className="detail-card-top">
                <span className="metric-card-icon">
                  <Users className="metric-card-icon-svg" aria-hidden="true" />
                </span>
              </div>
              <strong>{actors.length}</strong>
              <span>Local runtime users with self-hosted browser access.</span>
            </article>
            <article className="detail-card">
              <div className="detail-card-top">
                <span className="metric-card-icon">
                  <ShieldCheck className="metric-card-icon-svg" aria-hidden="true" />
                </span>
              </div>
              <strong>{actors.filter((actor) => actor.status !== "disabled").length}</strong>
              <span>Active users currently allowed to sign into this runtime.</span>
            </article>
          </section>

          {error ? <div className="error-banner">{error}</div> : null}

          <section className="split-layout">
            <Panel
              title="Local users"
              eyebrow="Inventory"
              className="compact-panel"
              actions={<span className="chip">{loading ? "Syncing" : `${actors.length} users`}</span>}
            >
              {loading && actors.length === 0 ? (
                <div className="empty-box">Loading runtime users...</div>
              ) : actors.length === 0 ? (
                <PageEmpty
                  title="No runtime users"
                  message="Bootstrap created no local users yet. Create one from the panel on the right."
                />
              ) : (
                <div className="settings-user-list">
                  {actors.map((actor) => {
                    const selected = selectedActor?.id === actor.id;
                    return (
                      <button
                        key={actor.id}
                        className={`list-card settings-user-card ${selected ? "active" : ""}`.trim()}
                        type="button"
                        onClick={() => setSelectedActorId(actor.id)}
                      >
                        <div className="settings-user-card-head">
                          <div>
                            <strong>{actor.display_name || actor.username}</strong>
                            <span>@{actor.username}</span>
                          </div>
                          <span className={`status-pill ${actor.status === "disabled" ? "disabled" : "active"}`.trim()}>
                            {actorStatusLabel(actor.status)}
                          </span>
                        </div>
                        <span>{actor.email}</span>
                        <div className="tag-list">
                          {(actor.roles || []).map((role) => (
                            <span key={`${actor.id}-${role}`} className="tag">
                              {roleLabel(role)}
                            </span>
                          ))}
                        </div>
                        <small>Password updated {formatDateTime(actor.password_updated_at)}</small>
                      </button>
                    );
                  })}
                </div>
              )}
            </Panel>

            <div className="detail-stack">
              <Panel title="Create user" eyebrow="Local auth" className="compact-panel">
                <form className="form-grid" onSubmit={handleCreateActor}>
                  <label className="field">
                    <span>Username</span>
                    <input
                      className="text-input"
                      name="username"
                      type="text"
                      autoComplete="off"
                      value={createForm.username}
                      onChange={(event) =>
                        setCreateForm((current) => ({ ...current, username: event.target.value }))
                      }
                      placeholder="analyst-one"
                      disabled={createState.submitting}
                      required
                    />
                  </label>
                  <label className="field">
                    <span>Email</span>
                    <input
                      className="text-input"
                      name="email"
                      type="email"
                      autoComplete="off"
                      value={createForm.email}
                      onChange={(event) =>
                        setCreateForm((current) => ({ ...current, email: event.target.value }))
                      }
                      placeholder="analyst@example.com"
                      disabled={createState.submitting}
                      required
                    />
                  </label>
                  <label className="field field-full">
                    <span>Display name</span>
                    <input
                      className="text-input"
                      name="display_name"
                      type="text"
                      autoComplete="off"
                      value={createForm.display_name}
                      onChange={(event) =>
                        setCreateForm((current) => ({ ...current, display_name: event.target.value }))
                      }
                      placeholder="Analyst One"
                      disabled={createState.submitting}
                    />
                  </label>
                  <label className="field field-full">
                    <span>Temporary password</span>
                    <input
                      className="text-input"
                      name="password"
                      type="password"
                      autoComplete="new-password"
                      value={createForm.password}
                      onChange={(event) =>
                        setCreateForm((current) => ({ ...current, password: event.target.value }))
                      }
                      placeholder="At least 8 characters"
                      disabled={createState.submitting}
                      required
                    />
                  </label>
                  <div className="field field-full">
                    <span>Roles</span>
                    <div className="field-pill-list">
                      {RUNTIME_ROLES.map((role) => (
                        <button
                          key={`create-${role.value}`}
                          className={`field-pill ${createForm.roles.includes(role.value) ? "active" : ""}`.trim()}
                          type="button"
                          onClick={() =>
                            setCreateForm((current) => ({
                              ...current,
                              roles: updateRoleList(current.roles, role.value),
                            }))
                          }
                          disabled={createState.submitting}
                        >
                          {role.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  {createState.error ? <div className="error-banner field-full">{createState.error}</div> : null}
                  {createState.success ? <div className="callout success field-full">{createState.success}</div> : null}
                  <div className="settings-form-actions field-full">
                    <button className="primary-button" type="submit" disabled={createState.submitting}>
                      <UserPlus className="button-icon" aria-hidden="true" />
                      {createState.submitting ? "Creating user..." : "Create user"}
                    </button>
                  </div>
                </form>
              </Panel>

              <Panel
                title={selectedActor ? `Manage ${selectedActor.username}` : "Select a user"}
                eyebrow="Access"
                className="compact-panel"
              >
                {!selectedActor ? (
                  <PageEmpty
                    title="No user selected"
                    message="Choose a runtime user to update roles, disable access, or reset the password."
                  />
                ) : (
                  <div className="detail-stack">
                    <div className="callout settings-user-summary">
                      <strong>{selectedActor.display_name || selectedActor.username}</strong>
                      <span>{selectedActor.email}</span>
                      <div className="inline-notes">
                        <span>{selectedActor.actor_type}</span>
                        <span>{actorStatusLabel(selectedActor.status)}</span>
                        <span>Updated {formatDateTime(selectedActor.updated_at)}</span>
                      </div>
                    </div>

                    <form className="detail-stack" onSubmit={handleSaveAccess}>
                      <div className="field">
                        <span>Roles</span>
                        <div className="field-pill-list">
                          {RUNTIME_ROLES.map((role) => (
                            <button
                              key={`edit-${role.value}`}
                              className={`field-pill ${accessForm.roles.includes(role.value) ? "active" : ""}`.trim()}
                              type="button"
                              onClick={() =>
                                setAccessForm((current) => ({
                                  ...current,
                                  roles: updateRoleList(current.roles, role.value),
                                }))
                              }
                              disabled={accessState.submitting}
                            >
                              {role.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="settings-inline-actions">
                        <button
                          className={`ghost-button ${accessForm.status === "disabled" ? "danger-button" : ""}`.trim()}
                          type="button"
                          onClick={() =>
                            setAccessForm((current) => ({
                              ...current,
                              status: current.status === "disabled" ? "active" : "disabled",
                            }))
                          }
                          disabled={accessState.submitting}
                        >
                          {accessForm.status === "disabled" ? (
                            <>
                              <ShieldCheck className="button-icon" aria-hidden="true" />
                              Enable user
                            </>
                          ) : (
                            <>
                              <ShieldOff className="button-icon" aria-hidden="true" />
                              Disable user
                            </>
                          )}
                        </button>
                        <span className={`status-pill ${accessForm.status === "disabled" ? "disabled" : "active"}`.trim()}>
                          {actorStatusLabel(accessForm.status)}
                        </span>
                      </div>

                      {accessState.error ? <div className="error-banner">{accessState.error}</div> : null}
                      {accessState.success ? <div className="callout success">{accessState.success}</div> : null}
                      <div className="settings-form-actions">
                        <button className="primary-button" type="submit" disabled={accessState.submitting}>
                          {accessState.submitting ? "Saving access..." : "Save access changes"}
                        </button>
                      </div>
                    </form>

                    <form className="detail-stack" onSubmit={handleResetPassword}>
                      <label className="field">
                        <span>New password</span>
                        <input
                          className="text-input"
                          type="password"
                          autoComplete="new-password"
                          value={passwordForm.password}
                          onChange={(event) =>
                            setPasswordForm((current) => ({ ...current, password: event.target.value }))
                          }
                          placeholder="Set a new local password"
                          disabled={passwordState.submitting}
                          required
                        />
                      </label>
                      <label className="checkbox-field">
                        <input
                          type="checkbox"
                          checked={passwordForm.must_rotate_password}
                          onChange={(event) =>
                            setPasswordForm((current) => ({
                              ...current,
                              must_rotate_password: event.target.checked,
                            }))
                          }
                          disabled={passwordState.submitting}
                        />
                        <span>Require password rotation on next admin review</span>
                      </label>
                      {passwordState.error ? <div className="error-banner">{passwordState.error}</div> : null}
                      {passwordState.success ? <div className="callout success">{passwordState.success}</div> : null}
                      <div className="settings-form-actions">
                        <button className="ghost-button" type="submit" disabled={passwordState.submitting}>
                          <KeyRound className="button-icon" aria-hidden="true" />
                          {passwordState.submitting ? "Resetting password..." : "Reset password"}
                        </button>
                      </div>
                    </form>
                  </div>
                )}
              </Panel>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

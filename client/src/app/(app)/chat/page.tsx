export default function ChatIndexPage() {
  return (
    <div className="flex min-h-full flex-col gap-6 px-6 py-10 text-[color:var(--text-secondary)] transition-colors sm:px-10 lg:px-14">
      <section className="surface-panel rounded-3xl p-6 shadow-soft">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--text-muted)]">Chats</p>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-[color:var(--text-primary)]">Recent chats</h1>
            <p className="text-sm text-[color:var(--text-secondary)]">
              This stub lists your recent conversations. Replace it with live conversation history to jump back into
              threads instantly.
            </p>
          </div>
        </div>
      </section>

      <section className="surface-panel flex flex-1 flex-col items-center justify-center rounded-3xl p-10 text-center shadow-soft">
        <div className="max-w-md space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] px-4 py-1 text-xs font-medium text-[color:var(--text-secondary)]">
            Coming soon
          </div>
          <h2 className="text-xl font-semibold text-[color:var(--text-primary)]">No chats yet</h2>
          <p className="text-sm text-[color:var(--text-muted)]">
            Start a new conversation from the dashboard to see it appear here. We&apos;ll keep your most recent sessions in
            sync so you can resume investigations quickly.
          </p>
        </div>
      </section>
    </div>
  );
}

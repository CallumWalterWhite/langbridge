import Link from 'next/link';

import { ThemeToggle } from '@/components/ThemeToggle';
import { LogoutButton } from '@/components/LogoutButton';

import { DashboardCards } from './_components/DashboardCards';

export const metadata = {
  title: 'Dashboard | LangBridge',
};

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen bg-[color:var(--shell-bg)] text-[color:var(--text-primary)] transition-colors">
      <aside className="hidden w-72 flex-col border-r border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-6 text-[color:var(--text-secondary)] shadow-soft lg:flex">
        <Link
          href="/chat"
          className="inline-flex items-center justify-center rounded-full border border-[color:var(--border-strong)] bg-[color:var(--panel-alt)] px-4 py-2 text-sm font-semibold text-[color:var(--text-primary)] transition hover:border-[color:var(--border-strong-hover)] hover:text-[color:var(--text-primary)]"
        >
          + New conversation
        </Link>
        <nav className="mt-8 space-y-1 text-sm">
          <Link className="block rounded-lg border border-[color:var(--border-strong)] bg-[color:var(--panel-alt)] px-3 py-2 font-medium text-[color:var(--text-primary)]" href="/dashboard">
            Agentic workspace
          </Link>
          <Link className="block rounded-lg px-3 py-2 text-[color:var(--text-secondary)] transition hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]" href="/datasources">
            Data connections
          </Link>
          <Link className="block rounded-lg px-3 py-2 text-[color:var(--text-secondary)] transition hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]" href="/agents">
          <Link className="block rounded-lg px-3 py-2 text-[color:var(--text-secondary)] transition hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]" href="/organizations">
            Organizations & projects
          </Link>
            Agents & playbooks
          </Link>
          <Link className="block rounded-lg px-3 py-2 text-[color:var(--text-secondary)] transition hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]" href="/chat">
            Conversations
          </Link>
          <Link className="block rounded-lg px-3 py-2 text-[color:var(--text-secondary)] transition hover:bg-[color:var(--panel-alt)] hover:text-[color:var(--text-primary)]" href="/settings">
            Settings
          </Link>
        </nav>
        <div className="mt-10 rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-alt)] p-4 text-xs leading-relaxed text-[color:var(--text-secondary)]">
          Your LangBridge copilot stitches structured data, docs, and SaaS telemetry into a single reasoning
          workspace. Drop new connectors or tune retrievers without leaving this panel.
        </div>
        <div className="mt-auto space-y-4 text-xs text-[color:var(--text-muted)]">
          <Link href="/docs" className="inline-flex items-center gap-2 transition hover:text-[color:var(--text-primary)]">
            Read documentation
          </Link>
          <Link href="/support" className="inline-flex items-center gap-2 transition hover:text-[color:var(--text-primary)]">
            Support & feedback
          </Link>
        </div>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-6 py-4 text-[color:var(--text-secondary)] shadow-soft backdrop-blur">
          <div>
            <h1 className="text-lg font-semibold text-[color:var(--text-primary)]">LangBridge Copilot</h1>
            <p className="text-sm">Ask across every data source. Automate the follow-ups.</p>
          </div>
          <div className="inline-flex items-center gap-3">
            <ThemeToggle size="sm" />
            <LogoutButton />
            <Link
              href="/docs/whats-new"
              className="hidden rounded-full border border-[color:var(--border-strong)] px-3 py-1 text-xs font-medium text-[color:var(--text-secondary)] transition hover:border-[color:var(--border-strong-hover)] hover:text-[color:var(--text-primary)] md:inline-flex"
            >
              What&apos;s new
            </Link>
          </div>
        </header>
        <div className="flex-1 overflow-y-auto">
          <DashboardCards />
        </div>
      </main>
    </div>
  );
}


import Link from 'next/link';

import { DashboardCards } from './_components/DashboardCards';

export const metadata = {
  title: 'Dashboard | LangBridge',
};

export default function DashboardPage() {
  return (
    <section className="space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-slate-900 md:text-3xl">Welcome to LangBridge</h1>
          <p className="max-w-2xl text-sm text-slate-600 md:text-base">
            Connect your data, build agents, and start asking questions.
          </p>
        </div>
        <Link
          href="/docs"
          className="text-sm font-medium text-slate-500 transition hover:text-slate-900"
          aria-label="Need help? Read the docs"
        >
          Need help?
        </Link>
      </header>
      <DashboardCards />
    </section>
  );
}

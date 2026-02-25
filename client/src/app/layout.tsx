import type { ReactNode } from 'react';

import './globals.css';
import { ThemeProvider } from './theme-provider';

export const metadata = { title: 'LangBridge' };
export const dynamic = 'force-dynamic';

const themeInitScript = `
if (typeof window !== 'undefined') {
  let theme = 'dark';
  try {
    const stored = localStorage.getItem('langbridge-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    theme = stored === 'light' || stored === 'dark' ? stored : prefersDark ? 'dark' : 'light';
  } catch {}
  document.documentElement.dataset.theme = theme;
  document.documentElement.classList.toggle('dark', theme === 'dark');
}
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  const backendUrl = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? '';
  const runtimeConfigScript = `window.__LANGBRIDGE_BACKEND_URL__ = ${JSON.stringify(backendUrl)};`;

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: runtimeConfigScript }} />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body
        suppressHydrationWarning
        className="min-h-screen bg-[color:var(--app-bg)] font-sans text-[color:var(--text-primary)] antialiased transition-colors"
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}

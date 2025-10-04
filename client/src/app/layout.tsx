import type { ReactNode } from 'react';
import Script from 'next/script';

import './globals.css';
import { ThemeProvider } from './theme-provider';

export const metadata = { title: 'LangBridge' };

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
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-[color:var(--app-bg)] font-sans text-[color:var(--text-primary)] antialiased transition-colors">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
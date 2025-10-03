import type { ReactNode } from 'react';

import './globals.css';
import { ThemeProvider } from './theme-provider';

export const metadata = { title: 'LangBridge' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-[color:var(--app-bg)] font-sans text-[color:var(--text-primary)] antialiased transition-colors">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}

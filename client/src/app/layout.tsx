import type { ReactNode } from 'react';

import './globals.css';

export const metadata = { title: 'LangBridge' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white font-sans text-slate-900 antialiased">{children}</body>
    </html>
  );
}

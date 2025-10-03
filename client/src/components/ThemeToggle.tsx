'use client';

import { useMemo } from 'react';
import { MoonStar, SunMedium } from 'lucide-react';

import { useTheme } from '@/app/theme-provider';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  className?: string;
  size?: 'sm' | 'md';
}

export function ThemeToggle({ className, size = 'md' }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();

  const dimensions = useMemo(() => {
    switch (size) {
      case 'sm':
        return 'h-8 px-3 text-xs';
      case 'md':
      default:
        return 'h-9 px-4 text-sm';
    }
  }, [size]);

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn(
        'inline-flex items-center gap-2 rounded-full border border-[color:var(--border-strong)] bg-[color:var(--panel-alt)] font-medium text-[color:var(--text-secondary)] transition hover:border-[color:var(--border-strong-hover)] hover:text-[color:var(--text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]',
        dimensions,
        className,
      )}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
    >
      {theme === 'dark' ? (
        <>
          <SunMedium className="h-4 w-4" aria-hidden="true" />
          Light mode
        </>
      ) : (
        <>
          <MoonStar className="h-4 w-4" aria-hidden="true" />
          Dark mode
        </>
      )}
    </button>
  );
}

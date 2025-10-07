'use client';

import * as React from 'react';

import { cn } from '@/lib/utils';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  placeholder?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  function Select({ className, children, placeholder, defaultValue, ...props }, ref) {
    return (
      <select
        ref={ref}
        defaultValue={defaultValue ?? ''}
        className={cn(
         'flex h-10 w-full appearance-none rounded-md border border-slate-200 bg-white text-slate-900 px-3 py-2 text-sm shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50',
         'dark:bg-slate-800 dark:border-slate-700 dark:text-white',
         className
        )}
        {...props}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {children}
      </select>
    );
  },
);

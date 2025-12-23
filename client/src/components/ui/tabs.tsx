'use client';

import * as React from 'react';

import { cn } from '@/lib/utils';

type TabsContextValue = {
  value: string;
  setValue: (value: string) => void;
};

const TabsContext = React.createContext<TabsContextValue | null>(null);

export interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultValue: string;
  value?: string;
  onValueChange?: (value: string) => void;
}

export function Tabs({ defaultValue, value: controlledValue, onValueChange, className, children, ...props }: TabsProps) {
  const isControlled = controlledValue !== undefined;
  const [uncontrolledValue, setUncontrolledValue] = React.useState(defaultValue);
  const value = isControlled ? controlledValue : uncontrolledValue;

  const setValue = React.useCallback(
    (nextValue: string) => {
      if (!isControlled) {
        setUncontrolledValue(nextValue);
      }
      onValueChange?.(nextValue);
    },
    [isControlled, onValueChange],
  );

  return (
    <TabsContext.Provider value={{ value, setValue }}>
      <div className={className} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

function useTabsContext(component: string) {
  const context = React.useContext(TabsContext);
  if (!context) {
    throw new Error(`${component} must be used within <Tabs>`);
  }
  return context;
}

export const TabsList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  function TabsList({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        role="tablist"
        className={cn(
          'inline-flex items-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-1 text-sm shadow-soft',
          className,
        )}
        {...props}
      />
    );
  },
);

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
  function TabsTrigger({ className, value, children, ...props }, ref) {
    const tabs = useTabsContext('TabsTrigger');
    const isActive = tabs.value === value;

    return (
      <button
        ref={ref}
        type="button"
        role="tab"
        aria-selected={isActive}
        onClick={() => tabs.setValue(value)}
        className={cn(
          'inline-flex min-w-[120px] items-center justify-center rounded-full px-3 py-1.5 font-medium transition',
          isActive
            ? 'bg-[color:var(--panel-alt)] text-[color:var(--text-primary)] shadow-sm'
            : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]',
          className,
        )}
        {...props}
      >
        {children}
      </button>
    );
  },
);

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

export const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
  function TabsContent({ className, value, children, ...props }, ref) {
    const tabs = useTabsContext('TabsContent');
    if (tabs.value !== value) {
      return null;
    }

    return (
      <div
        ref={ref}
        role="tabpanel"
        className={cn('mt-6', className)}
        {...props}
      >
        {children}
      </div>
    );
  },
);

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
        className={cn('inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1 text-sm', className)}
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
          'inline-flex min-w-[120px] items-center justify-center rounded-md px-3 py-1.5 font-medium transition',
          isActive ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900',
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

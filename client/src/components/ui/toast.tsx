'use client';

import * as React from 'react';

import { cn } from '@/lib/utils';

export type ToastVariant = 'default' | 'destructive';

export interface ToastOptions {
  id?: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

type ToastContextValue = {
  toast: (options: ToastOptions) => void;
  dismiss: (id: string) => void;
};

type ToastInternal = ToastOptions & { id: string };

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastInternal[]>([]);

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const toast = React.useCallback(
    ({ id, duration = 5000, ...options }: ToastOptions) => {
      const toastId = id ?? (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2));
      setToasts((prev) => [...prev, { id: toastId, duration, ...options }]);
      if (duration > 0) {
        window.setTimeout(() => dismiss(toastId), duration);
      }
    },
    [dismiss],
  );

  const value = React.useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-3">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={cn(
              'pointer-events-auto overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg',
              toast.variant === 'destructive' ? 'border-red-200 bg-red-50' : '',
            )}
          >
            <div className="flex items-start justify-between gap-3 p-4">
              <div>
                {toast.title ? <p className="text-sm font-semibold text-slate-900">{toast.title}</p> : null}
                {toast.description ? (
                  <p className="mt-1 text-sm text-slate-600">{toast.description}</p>
                ) : null}
              </div>
              <button
                type="button"
                className="rounded-md p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                onClick={() => dismiss(toast.id)}
                aria-label="Close notification"
              >
                ?
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within <ToastProvider>');
  }
  return context;
}

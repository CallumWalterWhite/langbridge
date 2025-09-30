'use client';

import * as React from 'react';
import { createPortal } from 'react-dom';

import { cn } from '@/lib/utils';

type DialogContextValue = {
  open: boolean;
  setOpen: (value: boolean) => void;
};

const DialogContext = React.createContext<DialogContextValue | null>(null);

export interface DialogProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

export function Dialog({ open: controlledOpen, defaultOpen, onOpenChange, children }: DialogProps) {
  const isControlled = controlledOpen !== undefined;
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen ?? false);
  const open = isControlled ? Boolean(controlledOpen) : uncontrolledOpen;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) {
        setUncontrolledOpen(next);
      }
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  return <DialogContext.Provider value={{ open, setOpen }}>{children}</DialogContext.Provider>;
}

function useDialogContext(component: string) {
  const context = React.useContext(DialogContext);
  if (!context) {
    throw new Error(`${component} must be used within <Dialog>`);
  }
  return context;
}

export interface DialogTriggerProps {
  children: React.ReactElement;
}

export function DialogTrigger({ children }: DialogTriggerProps) {
  const { setOpen } = useDialogContext('DialogTrigger');
  return React.cloneElement(children, {
    onClick: (event: React.MouseEvent) => {
      children.props.onClick?.(event);
      if (!event.defaultPrevented) {
        setOpen(true);
      }
    },
  });
}

export interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function DialogContent({ className, children, ...props }: DialogContentProps) {
  const { open, setOpen } = useDialogContext('DialogContent');
  const [mounted, setMounted] = React.useState(false);
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  React.useEffect(() => {
    if (!open) {
      return;
    }
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const firstFocusable = contentRef.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus({ preventScroll: true });
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown, { capture: true });
    return () => {
      document.removeEventListener('keydown', handleKeyDown, { capture: true });
      previouslyFocused?.focus({ preventScroll: true });
    };
  }, [open, setOpen]);

  const handleBackdropClick = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) {
        setOpen(false);
      }
    },
    [setOpen],
  );

  if (!mounted || !open) {
    return null;
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4"
      role="presentation"
      onMouseDown={handleBackdropClick}
    >
      <div
        ref={contentRef}
        role="dialog"
        aria-modal="true"
        className={cn(
          'max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl',
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}

export const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('mb-6 space-y-2', className)} {...props} />
);

export const DialogTitle = ({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
  <h2 className={cn('text-xl font-semibold leading-tight', className)} {...props} />
);

export const DialogDescription = ({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
  <p className={cn('text-sm text-slate-600', className)} {...props} />
);

export interface DialogFooterProps extends React.HTMLAttributes<HTMLDivElement> {}

export const DialogFooter = ({ className, ...props }: DialogFooterProps) => (
  <div className={cn('mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end', className)} {...props} />
);

export interface DialogCloseProps {
  children: React.ReactElement;
}

export function DialogClose({ children }: DialogCloseProps) {
  const { setOpen } = useDialogContext('DialogClose');
  return React.cloneElement(children, {
    onClick: (event: React.MouseEvent) => {
      children.props.onClick?.(event);
      if (!event.defaultPrevented) {
        setOpen(false);
      }
    },
  });
}

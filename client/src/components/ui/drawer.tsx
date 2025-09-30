'use client';

import * as React from 'react';
import { createPortal } from 'react-dom';

import { cn } from '@/lib/utils';

type DrawerContextValue = {
  open: boolean;
  setOpen: (value: boolean) => void;
};

const DrawerContext = React.createContext<DrawerContextValue | null>(null);

export interface DrawerProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

export function Drawer({ open: controlled, defaultOpen, onOpenChange, children }: DrawerProps) {
  const isControlled = controlled !== undefined;
  const [uncontrolled, setUncontrolled] = React.useState(defaultOpen ?? false);
  const open = isControlled ? Boolean(controlled) : uncontrolled;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) {
        setUncontrolled(next);
      }
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  return <DrawerContext.Provider value={{ open, setOpen }}>{children}</DrawerContext.Provider>;
}

function useDrawer(component: string) {
  const context = React.useContext(DrawerContext);
  if (!context) {
    throw new Error(`${component} must be used within <Drawer>`);
  }
  return context;
}

export interface DrawerTriggerProps {
  children: React.ReactElement;
}

export function DrawerTrigger({ children }: DrawerTriggerProps) {
  const { setOpen } = useDrawer('DrawerTrigger');
  return React.cloneElement(children, {
    onClick: (event: React.MouseEvent) => {
      children.props.onClick?.(event);
      if (!event.defaultPrevented) {
        setOpen(true);
      }
    },
  });
}

export interface DrawerContentProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
  side?: 'right' | 'left';
}

export function DrawerContent({ className, children, side = 'right', ...props }: DrawerContentProps) {
  const { open, setOpen } = useDrawer('DrawerContent');
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
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown, { capture: true });
    requestAnimationFrame(() => {
      contentRef.current?.focus({ preventScroll: true });
    });
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
      className="fixed inset-0 z-50 flex bg-slate-950/40"
      role="presentation"
      onMouseDown={handleBackdropClick}
    >
      <div className={cn('hidden flex-1', side === 'left' ? 'sm:block' : 'sm:hidden')} aria-hidden />
      <div
        ref={contentRef}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        className={cn(
          'ml-auto flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-xl transition',
          side === 'left' ? 'ml-0 mr-auto border-l-0 border-r' : 'ml-auto',
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

export interface DrawerCloseProps {
  children: React.ReactElement;
}

export function DrawerClose({ children }: DrawerCloseProps) {
  const { setOpen } = useDrawer('DrawerClose');
  return React.cloneElement(children, {
    onClick: (event: React.MouseEvent) => {
      children.props.onClick?.(event);
      if (!event.defaultPrevented) {
        setOpen(false);
      }
    },
  });
}

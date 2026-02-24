import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Plus } from 'lucide-react';
import { Responsive, WidthProvider } from 'react-grid-layout/legacy';
import type { Layout } from 'react-grid-layout/legacy';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import type { BiWidget, FieldOption, WidgetLayout } from '../types';
import { WidgetCard, WidgetCardSkeleton } from './WidgetCard';

const ResponsiveGridLayout = WidthProvider(Responsive);

type GridLayoutProps = {
  widgets: BiWidget[];
  activeWidgetId: string | null;
  isEditMode: boolean;
  onActivateWidget: (id: string) => void;
  onRemoveWidget: (id: string) => void;
  onDuplicateWidget: (id: string) => void;
  onAddWidget: () => void;
  onAddFieldToWidget: (widgetId: string, field: FieldOption, targetKind?: 'dimension' | 'measure') => void;
  onLayoutCommit: (layouts: Record<string, WidgetLayout>) => void;
};

export function GridLayout({
  widgets,
  activeWidgetId,
  isEditMode,
  onActivateWidget,
  onRemoveWidget,
  onDuplicateWidget,
  onAddWidget,
  onAddFieldToWidget,
  onLayoutCommit,
}: GridLayoutProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const layoutItems = useMemo(
    () =>
      widgets.map((widget) => ({
        i: widget.id,
        x: widget.layout.x,
        y: widget.layout.y,
        w: widget.layout.w,
        h: widget.layout.h,
        minW: widget.layout.minW ?? 2,
        minH: widget.layout.minH ?? 3,
      })),
    [widgets],
  );

  const addTileLayout = useMemo(() => {
    if (!isEditMode) {
      return null;
    }
    const nextY = layoutItems.reduce((maxY, item) => Math.max(maxY, item.y + item.h), 0);
    return {
      i: '__add_widget__',
      x: 0,
      y: nextY,
      w: 3,
      h: 4,
      static: true,
    };
  }, [isEditMode, layoutItems]);

  const combinedLayouts = useMemo(
    () => ({
      lg: addTileLayout ? [...layoutItems, addTileLayout] : layoutItems,
    }),
    [addTileLayout, layoutItems],
  );

  const handleLayoutStop = useCallback(
    (layout: Layout) => {
      const updates: Record<string, WidgetLayout> = {};
      layout.forEach((entry) => {
        if (entry.i === '__add_widget__') {
          return;
        }
        updates[entry.i] = {
          x: entry.x,
          y: entry.y,
          w: entry.w,
          h: entry.h,
          minW: entry.minW,
          minH: entry.minH,
        };
      });
      onLayoutCommit(updates);
    },
    [onLayoutCommit],
  );

  const handleKeyboardLayoutControl = useCallback(
    (event: KeyboardEvent<HTMLDivElement>, widget: BiWidget) => {
      if (!isEditMode || event.target !== event.currentTarget) {
        return;
      }

      const key = event.key;
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) {
        return;
      }

      event.preventDefault();
      const next = { ...widget.layout };
      const mutateSize = event.altKey;

      if (key === 'ArrowUp') {
        if (mutateSize) {
          next.h = Math.max(next.minH ?? 3, next.h - 1);
        } else {
          next.y = Math.max(0, next.y - 1);
        }
      }

      if (key === 'ArrowDown') {
        if (mutateSize) {
          next.h += 1;
        } else {
          next.y += 1;
        }
      }

      if (key === 'ArrowLeft') {
        if (mutateSize) {
          next.w = Math.max(next.minW ?? 2, next.w - 1);
        } else {
          next.x = Math.max(0, next.x - 1);
        }
      }

      if (key === 'ArrowRight') {
        if (mutateSize) {
          next.w += 1;
        } else {
          next.x += 1;
        }
      }

      onLayoutCommit({ [widget.id]: next });
    },
    [isEditMode, onLayoutCommit],
  );

  return (
    <div ref={containerRef} className="bi-grid-shell flex-1 overflow-auto px-5 pb-24 pt-4 lg:px-6">
      <ResponsiveGridLayout
        className="bi-grid-layout"
        layouts={combinedLayouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 2, xxs: 1 }}
        margin={[14, 14]}
        rowHeight={42}
        compactType="vertical"
        preventCollision
        allowOverlap={false}
        isBounded
        isDraggable={isEditMode}
        isResizable={isEditMode}
        draggableCancel="button, input, textarea, select, .bi-widget-nodrag"
        onDragStop={(layout: Layout) => handleLayoutStop(layout)}
        onResizeStop={(layout: Layout) => handleLayoutStop(layout)}
        resizeHandles={isEditMode ? ['se', 'e', 's'] : []}
        useCSSTransforms
      >
        {widgets.map((widget, index) => (
          <div
            key={widget.id}
            className={cn('bi-grid-item h-full min-h-0', widget.id === activeWidgetId ? 'is-active' : '')}
            tabIndex={isEditMode ? 0 : -1}
            onKeyDown={(event) => handleKeyboardLayoutControl(event, widget)}
            aria-label={`${widget.title}. Use arrow keys to move. Hold Alt and arrows to resize in edit mode.`}
          >
            <VirtualizedWidgetCard
              index={index}
              widget={widget}
              isActive={widget.id === activeWidgetId}
              isEditMode={isEditMode}
              onActivate={() => onActivateWidget(widget.id)}
              onRemove={() => onRemoveWidget(widget.id)}
              onDuplicate={() => onDuplicateWidget(widget.id)}
              onAddField={onAddFieldToWidget}
            />
          </div>
        ))}

        {isEditMode ? (
          <div key="__add_widget__" className="h-full min-h-0">
            <button
              type="button"
              onClick={onAddWidget}
              className="bi-add-widget group flex h-full min-h-[200px] w-full flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-[color:var(--border-strong)] bg-[color:var(--panel-alt)]/55 text-[color:var(--text-secondary)] transition hover:border-[color:var(--accent)] hover:bg-[color:var(--accent-soft)] hover:text-[color:var(--accent)]"
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]">
                <Plus className="h-5 w-5" />
              </span>
              <span className="text-xs font-semibold uppercase tracking-[0.18em]">Add Widget</span>
              <span className="text-[11px] text-[color:var(--text-muted)]">Drag fields or start from an empty card</span>
            </button>
          </div>
        ) : null}
      </ResponsiveGridLayout>

      {widgets.length === 0 ? (
        <div className="mt-6 flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-[color:var(--panel-border)] bg-[color:var(--panel-alt)]/50 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-[color:var(--text-primary)]">No widgets yet</p>
          <p className="max-w-sm text-xs text-[color:var(--text-muted)]">
            Add a widget, then drag dimensions and measures from the left pane to build your first chart.
          </p>
          <Button size="sm" onClick={onAddWidget} className="rounded-full px-4" disabled={!isEditMode}>
            Add widget
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function VirtualizedWidgetCard({
  widget,
  isActive,
  isEditMode,
  onActivate,
  onRemove,
  onDuplicate,
  onAddField,
  index,
}: {
  widget: BiWidget;
  isActive: boolean;
  isEditMode: boolean;
  onActivate: () => void;
  onRemove: () => void;
  onDuplicate: () => void;
  onAddField: (widgetId: string, field: FieldOption, targetKind?: 'dimension' | 'measure') => void;
  index: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isVisible, setIsVisible] = useState(index < 10);

  useEffect(() => {
    if (index < 10) {
      setIsVisible(true);
    }
  }, [index]);

  useEffect(() => {
    if (index < 10) {
      return;
    }
    const node = containerRef.current;
    if (!node) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        setIsVisible(Boolean(entry?.isIntersecting));
      },
      { rootMargin: '360px 0px 360px 0px' },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [index]);

  return (
    <div ref={containerRef} className="h-full min-h-0">
      {isVisible ? (
        <WidgetCard
          widget={widget}
          isActive={isActive}
          isEditMode={isEditMode}
          onActivate={onActivate}
          onRemove={onRemove}
          onDuplicate={onDuplicate}
          onAddField={onAddField}
        />
      ) : (
        <WidgetCardSkeleton title={widget.title} />
      )}
    </div>
  );
}

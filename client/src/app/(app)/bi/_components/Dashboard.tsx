import type { BiWidget, FieldOption, FilterDraft, WidgetLayout } from '../types';
import { FilterBar } from './FilterBar';
import { GridLayout } from './GridLayout';

type DashboardProps = {
  widgets: BiWidget[];
  activeWidgetId: string | null;
  activeWidget: BiWidget | null;
  fields: FieldOption[];
  globalFilters: FilterDraft[];
  onGlobalFiltersChange: (filters: FilterDraft[]) => void;
  onApplyGlobalFilters: () => void;
  isEditMode: boolean;
  onActivateWidget: (id: string) => void;
  onRemoveWidget: (id: string) => void;
  onDuplicateWidget: (id: string) => void;
  onAddWidget: () => void;
  onAddFieldToWidget: (widgetId: string, field: FieldOption, targetKind?: 'dimension' | 'measure') => void;
  onLayoutCommit: (layouts: Record<string, WidgetLayout>) => void;
};

export function Dashboard({
  widgets,
  activeWidgetId,
  activeWidget,
  fields,
  globalFilters,
  onGlobalFiltersChange,
  onApplyGlobalFilters,
  isEditMode,
  onActivateWidget,
  onRemoveWidget,
  onDuplicateWidget,
  onAddWidget,
  onAddFieldToWidget,
  onLayoutCommit,
}: DashboardProps) {
  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <FilterBar
        fields={fields}
        globalFilters={globalFilters}
        onGlobalFiltersChange={onGlobalFiltersChange}
        onApplyFilters={onApplyGlobalFilters}
        activeWidget={activeWidget}
        isEditMode={isEditMode}
      />

      <GridLayout
        widgets={widgets}
        activeWidgetId={activeWidgetId}
        isEditMode={isEditMode}
        onActivateWidget={onActivateWidget}
        onRemoveWidget={onRemoveWidget}
        onDuplicateWidget={onDuplicateWidget}
        onAddWidget={onAddWidget}
        onAddFieldToWidget={onAddFieldToWidget}
        onLayoutCommit={onLayoutCommit}
      />
    </section>
  );
}

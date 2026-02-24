import { Button } from '@/components/ui/button';
import {
  Eye,
  PencilRuler,
  Play,
  Plus,
  Save,
  Settings,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react';
import { Select } from '@/components/ui/select';

type DashboardOption = {
  id: string;
  name: string;
};

interface BiHeaderProps {
  dashboards: DashboardOption[];
  activeDashboardId: string | null;
  onSelectDashboard: (dashboardId: string) => void;
  onCreateDashboard: () => void;
  onSaveDashboard: () => void;
  onDeleteDashboard: () => void;
  canDeleteDashboard: boolean;
  isSavingDashboard: boolean;
  dashboardDirty: boolean;
  onRunActive: () => void;
  onRunAll: () => void;
  onToggleGlobalConfig: () => void;
  isRunning: boolean;
  canRunActive: boolean;
  canRunAll: boolean;
  onToggleConfig: () => void;
  isEditMode: boolean;
  onToggleEditMode: () => void;
  title?: string;
}

export function BiHeader({
  dashboards,
  activeDashboardId,
  onSelectDashboard,
  onCreateDashboard,
  onSaveDashboard,
  onDeleteDashboard,
  canDeleteDashboard,
  isSavingDashboard,
  dashboardDirty,
  onRunActive,
  onRunAll,
  onToggleGlobalConfig,
  isRunning,
  canRunActive,
  canRunAll,
  onToggleConfig,
  isEditMode,
  onToggleEditMode,
  title = 'Sales Intelligence Dashboard',
}: BiHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--panel-border)] px-5 py-4 lg:px-6">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--text-muted)]">Workspace / BI Studio</p>
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-[color:var(--text-primary)]" title={title}>
              {title}
            </span>
            {dashboardDirty ? (
              <span className="rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-amber-700">
                Unsaved
              </span>
            ) : null}
          </div>
        </div>

        <Select
          value={activeDashboardId ?? ''}
          onChange={(event) => onSelectDashboard(event.target.value)}
          className="h-8 w-56 bg-[color:var(--panel-alt)] text-xs"
        >
          <option value="">Draft dashboard</option>
          {dashboards.map((dashboard) => (
            <option key={dashboard.id} value={dashboard.id}>
              {dashboard.name}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant={isEditMode ? 'default' : 'outline'}
          onClick={onToggleEditMode}
          className="gap-2 rounded-full px-4 text-[10px] font-bold uppercase tracking-wider"
          aria-pressed={isEditMode}
        >
          {isEditMode ? <PencilRuler className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          {isEditMode ? 'Edit mode' : 'View mode'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onCreateDashboard}
          className="gap-2 rounded-full px-4 text-[10px] font-bold uppercase tracking-wider"
        >
          <Plus className="h-3 w-3" />
          New
        </Button>
        <Button
          size="sm"
          onClick={onSaveDashboard}
          disabled={isSavingDashboard}
          className="gap-2 rounded-full px-5 text-[10px] font-bold uppercase tracking-wider"
        >
          <Save className="h-3 w-3" />
          {isSavingDashboard ? 'Saving' : 'Save'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onDeleteDashboard}
          disabled={!canDeleteDashboard}
          className="gap-2 rounded-full px-4 text-[10px] font-bold uppercase tracking-wider"
        >
          <Trash2 className="h-3 w-3" />
          Delete
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onRunAll}
          disabled={!canRunAll || isRunning}
          className="gap-2 rounded-full px-4 text-[10px] font-bold uppercase tracking-wider"
        >
          <Play className="h-3 w-3 fill-current" />
          Run all
        </Button>
        <Button
          size="sm"
          onClick={onRunActive}
          disabled={!canRunActive || isRunning}
          className="gap-2 rounded-full px-4 text-[10px] font-bold uppercase tracking-wider"
        >
          <Play className="h-3 w-3 fill-current" />
          Run active
        </Button>
        <div className="mx-1 h-6 w-px bg-[color:var(--panel-border)]" />
        <Button
          variant="outline"
          size="icon"
          className="h-9 w-9 rounded-full border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]"
          onClick={onToggleGlobalConfig}
          aria-label="Open global dashboard settings"
        >
          <SlidersHorizontal className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-9 w-9 rounded-full border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]"
          onClick={onToggleConfig}
          aria-label="Open widget settings"
        >
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}

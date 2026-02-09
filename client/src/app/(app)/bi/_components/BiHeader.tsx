import { Button } from '@/components/ui/button';
import { Save, Play, Plus, Settings, SlidersHorizontal, Trash2 } from 'lucide-react';
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
  title = 'Sales Intelligence Dashboard',
}: BiHeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-4 z-30 bg-transparent">
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Workspace</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-sm font-semibold text-foreground truncate max-w-[240px]" title={title}>
            {title}
          </span>
          {dashboardDirty ? (
            <span className="rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-amber-700">
              Unsaved
            </span>
          ) : null}
        </div>
        <Select
          value={activeDashboardId ?? ''}
          onChange={(event) => onSelectDashboard(event.target.value)}
          className="h-8 w-52 text-xs"
        >
          <option value="">Draft dashboard</option>
          {dashboards.map((dashboard) => (
            <option key={dashboard.id} value={dashboard.id}>
              {dashboard.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant="outline"
          onClick={onCreateDashboard}
          className="gap-2 rounded-full px-4 uppercase tracking-wider text-[10px] font-bold shadow-sm"
        >
          <Plus className="h-3 w-3" />
          New
        </Button>
        <Button
          size="sm"
          onClick={onSaveDashboard}
          disabled={isSavingDashboard}
          className="gap-2 rounded-full px-5 bg-primary text-primary-foreground hover:bg-primary/90 uppercase tracking-wider text-[10px] font-bold shadow-sm"
        >
          <Save className="h-3 w-3" />
          {isSavingDashboard ? 'Saving' : 'Save'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onDeleteDashboard}
          disabled={!canDeleteDashboard}
          className="gap-2 rounded-full px-4 uppercase tracking-wider text-[10px] font-bold shadow-sm"
        >
          <Trash2 className="h-3 w-3" />
          Delete
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onRunAll}
          disabled={!canRunAll || isRunning}
          className="gap-2 rounded-full px-5 uppercase tracking-wider text-[10px] font-bold shadow-sm"
        >
          <Play className="h-3 w-3 fill-current" />
          Run All
        </Button>
        <Button
          size="sm"
          onClick={onRunActive}
          disabled={!canRunActive || isRunning}
          className="gap-2 rounded-full px-5 bg-primary text-primary-foreground hover:bg-primary/90 uppercase tracking-wider text-[10px] font-bold shadow-sm"
        >
          <Play className="h-3 w-3 fill-current" />
          Run Active
        </Button>
        <div className="w-[1px] h-6 bg-border mx-1"></div>
        <Button variant="outline" size="icon" className="h-9 w-9 rounded-full border-border bg-background shadow-sm hover:text-primary" onClick={onToggleGlobalConfig}>
          <SlidersHorizontal className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" className="h-9 w-9 rounded-full border-border bg-background shadow-sm hover:text-primary" onClick={onToggleConfig}>
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}

import { Button } from '@/components/ui/button';
import { Play, Settings, SlidersHorizontal } from 'lucide-react';

interface BiHeaderProps {
  onRunActive: () => void;
  onRunAll: () => void;
  onToggleGlobalConfig: () => void;
  isRunning: boolean;
  canRunActive: boolean;
  canRunAll: boolean;
  onToggleConfig: () => void;
  title?: string;
}

export function BiHeader({ onRunActive, onRunAll, onToggleGlobalConfig, isRunning, canRunActive, canRunAll, onToggleConfig, title = "Sales Intelligence Dashboard" }: BiHeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-4 z-30 bg-transparent">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Workspace</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-sm font-semibold text-foreground">{title}</span>
        </div>
      </div>
      <div className="flex items-center gap-3">
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

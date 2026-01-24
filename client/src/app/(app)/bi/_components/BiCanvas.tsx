import { Plus } from 'lucide-react';
import { BiWidgetTile } from './BiWidgetTile';
import type { BiWidget, FieldOption } from '../types';

interface BiCanvasProps {
  widgets: BiWidget[];
  activeWidgetId: string | null;
  onActivateWidget: (id: string) => void;
  onRemoveWidget: (id: string) => void;
  onAddWidget: () => void;
  onAddFieldToWidget: (widgetId: string, field: FieldOption, targetKind?: 'dimension' | 'measure') => void;
}

export function BiCanvas({
  widgets,
  activeWidgetId,
  onActivateWidget,
  onRemoveWidget,
  onAddWidget,
  onAddFieldToWidget
}: BiCanvasProps) {
  
  return (
    <div className="flex-1 overflow-auto bg-muted/10 p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-6 auto-rows-[minmax(260px,auto)] grid-flow-dense pb-20">
        
        {widgets.map(widget => (
          <BiWidgetTile 
            key={widget.id}
            widget={widget}
            isActive={widget.id === activeWidgetId}
            onActivate={() => onActivateWidget(widget.id)}
            onRemove={() => onRemoveWidget(widget.id)}
            onAddField={onAddFieldToWidget}
          />
        ))}

        {/* Add Widget Placeholder */}
        <button 
          onClick={onAddWidget}
          className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-border/60 hover:border-primary/50 hover:bg-primary/5 transition-all min-h-[300px] text-muted-foreground hover:text-primary group"
        >
          <div className="h-12 w-12 rounded-full bg-background border border-border group-hover:border-primary/30 flex items-center justify-center shadow-sm transition-colors">
            <Plus className="h-6 w-6" />
          </div>
          <span className="text-sm font-semibold">Add Widget</span>
        </button>

      </div>
    </div>
  );
}

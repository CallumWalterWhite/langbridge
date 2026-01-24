import { X, BarChart3, LineChart, PieChart as PieChartIcon, Table as TableIcon, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, LineChart as RechartsLine, Line, PieChart, Pie, Cell } from 'recharts';
import { cn } from '@/lib/utils';
import type { BiWidget, FieldOption } from '../types';

interface BiWidgetTileProps {
  widget: BiWidget;
  isActive: boolean;
  onActivate: () => void;
  onRemove: () => void;
  onAddField: (widgetId: string, field: FieldOption, targetKind?: 'dimension' | 'measure') => void;
}

export function BiWidgetTile({
  widget,
  isActive,
  onActivate,
  onRemove,
  onAddField
}: BiWidgetTileProps) {
  const sizeClassName = (() => {
    switch (widget.size) {
      case 'wide':
        return 'col-span-1 lg:col-span-2 row-span-1';
      case 'tall':
        return 'col-span-1 row-span-2';
      case 'large':
        return 'col-span-1 lg:col-span-2 row-span-2';
      default:
        return 'col-span-1 row-span-1';
    }
  })();

  const pieColors = [
    '#4f46e5',
    '#22c55e',
    '#f97316',
    '#0ea5e9',
    '#ec4899',
    '#a855f7',
  ];
  
  const hasData = widget.queryResult?.data && widget.queryResult.data.length > 0;
  const columnMetadata = widget.queryResult?.metadata ?? [];
  const columnLabelMap = new Map<string, string>();
  columnMetadata.forEach((entry) => {
    if (entry && typeof entry === 'object') {
      const column = entry.column as string | undefined;
      const name = entry.name as string | undefined;
      if (column && name) {
        columnLabelMap.set(column, name);
      }
    }
  });
  const getColumnLabel = (key: string) => columnLabelMap.get(key) ?? key;
  
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
  };

  const handleDrop = (e: React.DragEvent, targetKind?: 'dimension' | 'measure') => {
    e.preventDefault();
    e.stopPropagation();
    const data = e.dataTransfer.getData("application/json");
    if (data) {
      try {
        const field = JSON.parse(data) as FieldOption;
        onAddField(widget.id, field, targetKind);
      } catch (err) {
        console.error("Failed to parse dropped field", err);
      }
    }
  };

  const renderChart = () => {
    if (!hasData || !widget.queryResult) return null;
    const data = widget.queryResult.data;

    // Use widget.chartX / chartY if set, otherwise auto-pick first available
    const xKey = widget.chartX || Object.keys(data[0])[0];
    const yKey = widget.chartY || Object.keys(data[0]).find(k => k !== xKey) || Object.keys(data[0])[1];
    const yLabel = getColumnLabel(yKey);

    if (widget.type === 'bar') {
      return (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{fontSize: 10, fill: '#64748b'}} />
            <YAxis axisLine={false} tickLine={false} tick={{fontSize: 10, fill: '#64748b'}} />
            <Tooltip 
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)', fontSize: '12px' }}
              cursor={{ fill: '#f1f5f9' }}
            />
            <Bar dataKey={yKey} name={yLabel} fill="var(--primary)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      );
    }
    if (widget.type === 'line') {
      return (
        <ResponsiveContainer width="100%" height="100%">
          <RechartsLine data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey={xKey} axisLine={false} tickLine={false} tick={{fontSize: 10, fill: '#64748b'}} />
            <YAxis axisLine={false} tickLine={false} tick={{fontSize: 10, fill: '#64748b'}} />
            <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)', fontSize: '12px' }} />
            <Line type="monotone" dataKey={yKey} name={yLabel} stroke="var(--primary)" strokeWidth={2} dot={{r: 3, fill: 'var(--primary)', strokeWidth: 2, stroke: '#fff'}} />
          </RechartsLine>
        </ResponsiveContainer>
      );
    }
    if (widget.type === 'pie') {
      const resolvedYKey = yKey || xKey;
      const pieData = data.map((row) => ({
        name: String((row as Record<string, unknown>)[xKey]),
        value: Number((row as Record<string, unknown>)[resolvedYKey]) || 0,
      }));
      return (
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)', fontSize: '12px' }}
            />
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              innerRadius="35%"
              outerRadius="80%"
              paddingAngle={2}
            >
              {pieData.map((entry, index) => (
                <Cell key={`cell-${entry.name}-${index}`} fill={pieColors[index % pieColors.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      );
    }
    if (widget.type === 'table') {
        return (
            <div className="h-full w-full overflow-auto text-xs">
                <table className="w-full text-left">
                    <thead className="bg-muted/50 sticky top-0 text-muted-foreground font-semibold">
                        <tr>
                            {Object.keys(data[0]).map(k => (
                              <th key={k} className="px-3 py-2 whitespace-nowrap">{getColumnLabel(k)}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                        {data.slice(0, 50).map((row: Record<string, unknown>, i: number) => (
                            <tr key={i} className="hover:bg-muted/20">
                                {Object.values(row).map((v: unknown, j: number) => <td key={j} className="px-3 py-1.5 whitespace-nowrap text-foreground/80">{String(v)}</td>)}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )
    }
    return null;
  };

  return (
    <div 
      className={cn(
        "relative flex flex-col rounded-2xl border bg-background shadow-sm transition-all overflow-hidden group min-h-[280px]",
        sizeClassName,
        isActive 
          ? "ring-2 ring-primary border-transparent shadow-md z-10" 
          : "border-border hover:border-primary/30"
      )}
      onClick={onActivate}
      onDragOver={handleDragOver}
      onDrop={(e) => handleDrop(e)}
    >
        {/* Widget Header */}
        <div className="px-4 py-3 flex items-center justify-between border-b border-border/40 bg-muted/10">
            <div className="flex items-center gap-2 overflow-hidden flex-1">
                <div className={cn("p-1.5 rounded-md", isActive ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
                    {widget.type === 'bar' && <BarChart3 className="h-3.5 w-3.5" />}
                    {widget.type === 'line' && <LineChart className="h-3.5 w-3.5" />}
                    {widget.type === 'pie' && <PieChartIcon className="h-3.5 w-3.5" />}
                    {widget.type === 'table' && <TableIcon className="h-3.5 w-3.5" />}
                </div>
                <span className="text-sm font-semibold truncate">{widget.title}</span>
            </div>
            
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={(e) => { e.stopPropagation(); onRemove(); }}>
                    <X className="h-3.5 w-3.5" />
                </Button>
            </div>
        </div>

        {/* Chart Area */}
        <div className="flex-1 p-4 relative min-h-0">
            {widget.isLoading ? (
                <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur-sm z-10">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
            ) : null}

            {hasData ? (
                renderChart()
            ) : (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground/40 gap-3 border-2 border-dashed border-border/50 rounded-xl m-2">
                    {widget.type === 'bar' && <BarChart3 className="h-8 w-8" />}
                    {widget.type === 'line' && <LineChart className="h-8 w-8" />}
                    {widget.type === 'pie' && <PieChartIcon className="h-8 w-8" />}
                    {widget.type === 'table' && <TableIcon className="h-8 w-8" />}
                    <p className="text-xs font-medium">Drag fields here</p>
                </div>
            )}
        </div>
    </div>
  );
}

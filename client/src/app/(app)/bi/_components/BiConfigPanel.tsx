import { X, Plus, Trash2, Type, Hash } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FieldSelect } from './FieldSelect';
import { 
  ChartType,
  WidgetSize,
  FilterDraft, 
  OrderByDraft, 
  FILTER_OPERATORS, 
  TIME_GRAIN_OPTIONS, 
  DATE_PRESETS,
  FieldOption
} from '../types';

interface BiConfigPanelProps {
  onClose: () => void;
  // Widget Meta
  title: string;
  setTitle: (title: string) => void;
  // Visual Props
  chartX: string;
  setChartX: (x: string) => void;
  chartY: string;
  setChartY: (y: string) => void;
  chartType: ChartType;
  setChartType: (type: ChartType) => void;
  widgetSize: WidgetSize;
  setWidgetSize: (size: WidgetSize) => void;
  // Data Props
  fields: FieldOption[];
  selectedDimensions: string[];
  selectedMeasures: string[];
  onRemoveField: (id: string, kind: 'dimension' | 'measure') => void;
  filters: FilterDraft[];
  setFilters: (filters: FilterDraft[]) => void;
  orderBys: OrderByDraft[];
  setOrderBys: (orders: OrderByDraft[]) => void;
  limit: number;
  setLimit: (limit: number) => void;
  timeDimension: string;
  setTimeDimension: (id: string) => void;
  timeGrain: string;
  setTimeGrain: (grain: string) => void;
  timeRangePreset: string;
  setTimeRangePreset: (preset: string) => void;
  onExportCsv: () => void;
  onShowSql: () => void;
}

export function BiConfigPanel({
  onClose,
  title,
  setTitle,
  chartX,
  setChartX,
  chartY,
  setChartY,
  chartType,
  setChartType,
  widgetSize,
  setWidgetSize,
  fields,
  selectedDimensions,
  selectedMeasures,
  onRemoveField,
  filters,
  setFilters,
  orderBys,
  setOrderBys,
  limit,
  setLimit,
  timeDimension,
  setTimeDimension,
  timeGrain,
  setTimeGrain,
  timeRangePreset,
  setTimeRangePreset,
  onExportCsv,
  onShowSql
}: BiConfigPanelProps) {
  
  const timeFields = fields.filter(f => f.type === 'date' || f.type === 'timestamp' || f.kind === 'dimension'); 
  
  // Field lookup for labels
  const getFieldLabel = (id: string) => fields.find(f => f.id === id)?.label || id;

  const handleAddFilter = () => {
    setFilters([...filters, { 
      id: Math.random().toString(36).substr(2, 9), 
      member: fields[0]?.id || '', 
      operator: 'equals', 
      values: '' 
    }]);
  };

  const handleUpdateFilter = (id: string, updates: Partial<FilterDraft>) => {
    setFilters(filters.map(f => f.id === id ? { ...f, ...updates } : f));
  };

  const handleRemoveFilter = (id: string) => {
    setFilters(filters.filter(f => f.id !== id));
  };


  const handleAddOrder = () => {
    setOrderBys([...orderBys, { 
      id: Math.random().toString(36).substr(2, 9), 
      member: fields[0]?.id || '', 
      direction: 'desc' 
    }]);
  };

  const handleUpdateOrder = (id: string, updates: Partial<OrderByDraft>) => {
    setOrderBys(orderBys.map(o => o.id === id ? { ...o, ...updates } : o));
  };

  const handleRemoveOrder = (id: string) => {
    setOrderBys(orderBys.filter(o => o.id !== id));
  };

  return (
    <div className="flex flex-col h-full bg-background w-full">
      <div className="p-4 border-b border-[var(--border-light)] flex items-center justify-between bg-muted/10">
        <div className="flex-1 mr-4">
          <Input 
            value={title} 
            onChange={(e) => setTitle(e.target.value)} 
            className="h-8 font-semibold bg-transparent border-transparent hover:border-border focus:border-primary px-2 transition-colors"
            placeholder="Widget Title"
          />
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7 text-muted-foreground">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <Tabs defaultValue="data" className="flex-1 flex flex-col overflow-hidden">
        <div className="px-4 pt-4">
          <TabsList className="w-full grid grid-cols-2">
            <TabsTrigger value="data">Data & Logic</TabsTrigger>
            <TabsTrigger value="visual">Visuals</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="visual" className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          <section>
            <label className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground mb-4 block">Chart Type</label>
            <Select value={chartType} onChange={(e) => setChartType(e.target.value as ChartType)}>
              <option value="bar">Bar</option>
              <option value="line">Line</option>
              <option value="pie">Pie</option>
              <option value="table">Table</option>
            </Select>
          </section>

          <section>
            <label className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground mb-4 block">Widget Size</label>
            <Select value={widgetSize} onChange={(e) => setWidgetSize(e.target.value as WidgetSize)}>
              <option value="small">Small</option>
              <option value="wide">Wide</option>
              <option value="tall">Tall</option>
              <option value="large">Large</option>
            </Select>
          </section>

          <section>
            <label className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground mb-4 block">Field Mapping</label>
            {chartType === 'table' ? (
              <p className="text-xs text-muted-foreground">
                Tables show all returned columns. Use query settings to control columns and order.
              </p>
            ) : (
              <div className="space-y-4">
                <div>
                  <span className="text-[11px] font-semibold text-muted-foreground mb-1.5 block">X Field</span>
                  <Select 
                    value={chartX} 
                    onChange={(e) => setChartX(e.target.value)}
                    placeholder="Select X Axis"
                  >
                    <option value="">Auto</option>
                    {selectedDimensions.map(id => (
                      <option key={id} value={id}>{getFieldLabel(id)}</option>
                    ))}
                  </Select>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-muted-foreground mb-1.5 block">Y Field</span>
                  <Select 
                    value={chartY} 
                    onChange={(e) => setChartY(e.target.value)}
                    placeholder="Select Y Axis"
                  >
                     <option value="">Auto</option>
                     {selectedMeasures.map(id => (
                      <option key={id} value={id}>{getFieldLabel(id)}</option>
                    ))}
                  </Select>
                </div>
              </div>
            )}
          </section>

          <section>
            <label className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground mb-4 block">Palette</label>
            <div className="grid grid-cols-5 gap-3">
              <button className="aspect-square rounded-full bg-primary ring-2 ring-offset-2 ring-primary"></button>
              <button className="aspect-square rounded-full bg-blue-500 hover:ring-2 ring-blue-100 transition-all"></button>
              <button className="aspect-square rounded-full bg-orange-500 hover:ring-2 ring-orange-100 transition-all"></button>
              <button className="aspect-square rounded-full bg-pink-500 hover:ring-2 ring-pink-100 transition-all"></button>
              <button className="aspect-square rounded-full bg-slate-800 hover:ring-2 ring-slate-100 transition-all"></button>
            </div>
          </section>
        </TabsContent>

        <TabsContent value="data" className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          
          {/* Dimensions & Measures */}
          <section className="space-y-4">
             <div className="space-y-2">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                   <Type className="h-3 w-3" /> Dimensions
                </Label>
                {selectedDimensions.length === 0 && <div className="text-xs text-muted-foreground italic px-2">No dimensions selected</div>}
                <div className="space-y-1">
                   {selectedDimensions.map(id => (
                      <div key={id} className="flex items-center justify-between px-2 py-1.5 bg-muted/30 rounded-md text-xs border border-border group">
                         <span className="truncate">{getFieldLabel(id)}</span>
                         <button onClick={() => onRemoveField(id, 'dimension')} className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity">
                            <X className="h-3 w-3" />
                         </button>
                      </div>
                   ))}
                </div>
             </div>

             <div className="space-y-2">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                   <Hash className="h-3 w-3" /> Measures
                </Label>
                {selectedMeasures.length === 0 && <div className="text-xs text-muted-foreground italic px-2">No measures selected</div>}
                <div className="space-y-1">
                   {selectedMeasures.map(id => (
                      <div key={id} className="flex items-center justify-between px-2 py-1.5 bg-muted/30 rounded-md text-xs border border-border group">
                         <span className="truncate">{getFieldLabel(id)}</span>
                         <button onClick={() => onRemoveField(id, 'measure')} className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity">
                            <X className="h-3 w-3" />
                         </button>
                      </div>
                   ))}
                </div>
             </div>
          </section>

          <div className="h-[1px] bg-border my-2"></div>

          {/* Time Dimension */}
          <section className="space-y-3">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Time Dimension</Label>
            <FieldSelect
              value={timeDimension}
              onChange={setTimeDimension}
              fields={timeFields}
              allowEmpty
              emptyLabel="None"
              placeholder="Select time field"
              className="h-9 text-xs"
              inputClassName="text-xs"
            />
            {timeDimension && (
              <div className="grid grid-cols-2 gap-2">
                 <Select 
                    value={timeGrain} 
                    onChange={(e) => setTimeGrain(e.target.value)}
                  >
                    {TIME_GRAIN_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </Select>
                  <Select 
                    value={timeRangePreset} 
                    onChange={(e) => setTimeRangePreset(e.target.value)}
                  >
                    <option value="">Custom</option>
                    {DATE_PRESETS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </Select>
              </div>
            )}
          </section>

          {/* Filters */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
               <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Filters</Label>
               <Button variant="outline" size="sm" onClick={handleAddFilter} className="h-6 gap-1 px-2 text-xs">
                 <Plus className="h-3 w-3" /> Add
               </Button>
            </div>
            {filters.length === 0 && <div className="text-xs text-muted-foreground italic">No filters applied</div>}
            <div className="space-y-2">
              {filters.map(filter => (
                <div key={filter.id} className="bg-muted/30 p-2 rounded-lg space-y-2 border border-border">
                  <div className="flex items-center gap-2">
                    <FieldSelect
                      value={filter.member}
                      onChange={(value) => handleUpdateFilter(filter.id, { member: value })}
                      fields={fields}
                      className="h-7 text-xs"
                      inputClassName="text-xs"
                    />
                    <Button variant="ghost" size="icon" onClick={() => handleRemoveFilter(filter.id)} className="h-7 w-7 text-destructive hover:bg-destructive/10">
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Select 
                      value={filter.operator} 
                      onChange={(e) => handleUpdateFilter(filter.id, { operator: e.target.value })}
                      className="h-7 text-xs"
                    >
                      {FILTER_OPERATORS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
                    </Select>
                    <Input 
                      value={filter.values} 
                      onChange={(e) => handleUpdateFilter(filter.id, { values: e.target.value })}
                      className="h-7 text-xs"
                      placeholder="Value"
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>


          {/* Sorting */}
           <section className="space-y-3">
            <div className="flex items-center justify-between">
               <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Sorting</Label>
               <Button variant="outline" size="sm" onClick={handleAddOrder} className="h-6 gap-1 px-2 text-xs">
                 <Plus className="h-3 w-3" /> Add
               </Button>
            </div>
            {orderBys.length === 0 && <div className="text-xs text-muted-foreground italic">Default sorting</div>}
            <div className="space-y-2">
              {orderBys.map(order => (
                <div key={order.id} className="flex items-center gap-2 bg-muted/30 p-1.5 rounded-lg border border-border">
                   <FieldSelect
                      value={order.member}
                      onChange={(value) => handleUpdateOrder(order.id, { member: value })}
                      fields={fields}
                      className="h-7 text-xs flex-1"
                      inputClassName="text-xs"
                    />
                    <Select 
                      value={order.direction} 
                      onChange={(e) => handleUpdateOrder(order.id, { direction: e.target.value as 'asc' | 'desc' })}
                      className="h-7 text-xs w-20"
                    >
                      <option value="asc">Asc</option>
                      <option value="desc">Desc</option>
                    </Select>
                    <Button variant="ghost" size="icon" onClick={() => handleRemoveOrder(order.id)} className="h-7 w-7 text-muted-foreground">
                      <Trash2 className="h-3 w-3" />
                    </Button>
                </div>
              ))}
            </div>
          </section>

          {/* Limit */}
          <section className="space-y-3">
             <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Row Limit</Label>
             <Input 
               type="number" 
               value={limit} 
               onChange={(e) => setLimit(Number(e.target.value))} 
               className="h-8 text-sm"
               min={1}
               max={10000}
             />
          </section>

          {/* Actions */}
          <section className="pt-4 border-t border-border space-y-2">
            <Button variant="outline" size="sm" className="w-full justify-start" onClick={onExportCsv}>
               Download CSV
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start" onClick={onShowSql}>
               View SQL
            </Button>
          </section>

        </TabsContent>
      </Tabs>
    </div>
  );
}

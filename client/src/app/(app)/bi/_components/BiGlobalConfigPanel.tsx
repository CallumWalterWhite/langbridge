import { X, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { FILTER_OPERATORS } from '../types';
import type { FieldOption, FilterDraft } from '../types';
import { FieldSelect } from './FieldSelect';

interface BiGlobalConfigPanelProps {
  onClose: () => void;
  workspaceName: string;
  setWorkspaceName: (name: string) => void;
  fields: FieldOption[];
  globalFilters: FilterDraft[];
  setGlobalFilters: (filters: FilterDraft[]) => void;
}

export function BiGlobalConfigPanel({
  onClose,
  workspaceName,
  setWorkspaceName,
  fields,
  globalFilters,
  setGlobalFilters,
}: BiGlobalConfigPanelProps) {
  const handleAddGlobalFilter = () => {
    setGlobalFilters([
      ...globalFilters,
      {
        id: Math.random().toString(36).substr(2, 9),
        member: fields[0]?.id || '',
        operator: 'equals',
        values: '',
      },
    ]);
  };

  const handleUpdateGlobalFilter = (id: string, updates: Partial<FilterDraft>) => {
    setGlobalFilters(globalFilters.map(f => (f.id === id ? { ...f, ...updates } : f)));
  };

  const handleRemoveGlobalFilter = (id: string) => {
    setGlobalFilters(globalFilters.filter(f => f.id !== id));
  };

  return (
    <div className="flex flex-col h-full bg-background w-full">
      <div className="p-4 border-b border-[var(--border-light)] flex items-center justify-between bg-muted/10">
        <div className="flex-1 mr-4">
          <Input
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            className="h-8 font-semibold bg-transparent border-transparent hover:border-border focus:border-primary px-2 transition-colors"
            placeholder="Workspace name"
          />
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7 text-muted-foreground">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Global Filters</Label>
            <Button variant="outline" size="sm" onClick={handleAddGlobalFilter} className="h-6 gap-1 px-2 text-xs">
              <Plus className="h-3 w-3" /> Add
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">Applies to every widget in this dashboard.</p>
          {globalFilters.length === 0 && (
            <div className="text-xs text-muted-foreground italic">No global filters applied</div>
          )}
          <div className="space-y-2">
            {globalFilters.map(filter => (
              <div key={filter.id} className="bg-muted/30 p-2 rounded-lg space-y-2 border border-border">
                <div className="flex items-center gap-2">
                  <FieldSelect
                    value={filter.member}
                    onChange={(value) => handleUpdateGlobalFilter(filter.id, { member: value })}
                    fields={fields}
                    className="h-7 text-xs"
                    inputClassName="text-xs"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveGlobalFilter(filter.id)}
                    className="h-7 w-7 text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Select
                    value={filter.operator}
                    onChange={(e) => handleUpdateGlobalFilter(filter.id, { operator: e.target.value })}
                    className="h-7 text-xs"
                  >
                    {FILTER_OPERATORS.map(op => (
                      <option key={op.value} value={op.value}>{op.label}</option>
                    ))}
                  </Select>
                  <Input
                    value={filter.values}
                    onChange={(e) => handleUpdateGlobalFilter(filter.id, { values: e.target.value })}
                    className="h-7 text-xs"
                    placeholder="Value"
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

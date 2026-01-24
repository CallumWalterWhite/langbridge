import { useState } from 'react';
import { Search, ChevronDown, Plus, Hash, Type, Calendar, List } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { FieldOption, TableGroup } from '../types';
import type { SemanticModelRecord } from '@/orchestration/semanticModels/types';

interface BiSidebarProps {
  semanticModels: SemanticModelRecord[];
  selectedModelId: string;
  onSelectModel: (id: string) => void;
  tableGroups: TableGroup[];
  fieldSearch: string;
  onFieldSearchChange: (value: string) => void;
  onAddField: (field: FieldOption) => void;
  selectedFields: Set<string>;
}

export function BiSidebar({
  semanticModels,
  selectedModelId,
  onSelectModel,
  tableGroups,
  fieldSearch,
  onFieldSearchChange,
  onAddField,
  selectedFields
}: BiSidebarProps) {
  const [isModelListOpen, setIsModelListOpen] = useState(false);

  const selectedModel = semanticModels.find(m => m.id === selectedModelId);

  const renderFieldIcon = (kind: string) => {
    switch (kind) {
      case 'dimension': return <Type className="h-3 w-3 text-blue-500" />;
      case 'measure': return <Hash className="h-3 w-3 text-orange-500" />;
      case 'date': return <Calendar className="h-3 w-3 text-green-500" />;
      default: return <List className="h-3 w-3 text-slate-500" />;
    }
  };

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col gap-4 h-[calc(100vh-6rem)] py-2 pl-2">
      {/* Model Card */}
      <div className="rounded-2xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] p-4 shadow-sm">
        <label className="text-[10px] font-bold text-[color:var(--text-muted)] uppercase tracking-widest mb-2 block">Data Source</label>
        <div className="relative">
          <Button 
            variant="outline" 
            className="w-full justify-between text-left font-normal bg-[color:var(--panel-alt)] border-0"
            onClick={() => setIsModelListOpen(!isModelListOpen)}
          >
            <span className="truncate">{selectedModel?.name || "Select Model"}</span>
            <ChevronDown className="h-4 w-4 opacity-50" />
          </Button>
          {isModelListOpen && (
            <div className="absolute top-full left-0 w-full mt-2 bg-[color:var(--panel-bg)] border border-[color:var(--panel-border)] rounded-xl shadow-lg z-50 max-h-60 overflow-y-auto p-1">
              {semanticModels.map(model => (
                <div 
                  key={model.id}
                  className={cn(
                    "px-3 py-2 text-sm cursor-pointer rounded-lg transition-colors",
                    model.id === selectedModelId 
                      ? "bg-[color:var(--accent-soft)] text-[color:var(--text-primary)]" 
                      : "hover:bg-[color:var(--panel-alt)] text-[color:var(--text-secondary)]"
                  )}
                  onClick={() => {
                    onSelectModel(model.id);
                    setIsModelListOpen(false);
                  }}
                >
                  {model.name}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Fields Panel */}
      <div className="flex-1 flex flex-col rounded-3xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] shadow-sm overflow-hidden">
        <div className="p-4 border-b border-[color:var(--panel-border)]">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-[color:var(--text-muted)]" />
            <Input 
              className="pl-9 h-9 text-xs bg-[color:var(--panel-alt)] border-0 focus-visible:ring-[color:var(--accent)]" 
              placeholder="Find fields..." 
              value={fieldSearch}
              onChange={(e) => onFieldSearchChange(e.target.value)}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          {tableGroups.map(group => (
            <div key={group.tableKey} className="space-y-2">
              <h4 className="text-[10px] font-bold text-[color:var(--text-muted)] uppercase tracking-widest px-1 truncate" title={group.name}>
                {group.name}
              </h4>
              
              <div className="space-y-1">
                 {group.dimensions.filter(f => f.label.toLowerCase().includes(fieldSearch.toLowerCase())).map(field => (
                   <FieldItem 
                     key={field.id} 
                     field={field} 
                     isSelected={selectedFields.has(field.id)}
                     onAdd={() => onAddField(field)}
                     icon={renderFieldIcon('dimension')}
                   />
                 ))}
                 {group.measures.filter(f => f.label.toLowerCase().includes(fieldSearch.toLowerCase())).map(field => (
                   <FieldItem 
                     key={field.id} 
                     field={field} 
                     isSelected={selectedFields.has(field.id)}
                     onAdd={() => onAddField(field)}
                     icon={renderFieldIcon('measure')}
                   />
                 ))}
              </div>
            </div>
          ))}
          {tableGroups.length === 0 && (
             <div className="text-xs text-[color:var(--text-muted)] text-center py-4">No fields found</div>
          )}
        </div>
      </div>
    </aside>
  );
}

function FieldItem({ field, isSelected, onAdd, icon }: { field: FieldOption, isSelected: boolean, onAdd: () => void, icon: React.ReactNode }) {
  return (
    <div 
      className={cn(
        "group flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-all border",
        isSelected 
          ? "bg-[color:var(--accent-soft)] border-[color:var(--accent)] text-[color:var(--text-primary)] font-medium shadow-sm" 
          : "border-transparent hover:bg-[color:var(--panel-alt)] text-[color:var(--text-secondary)]"
      )}
      onClick={onAdd}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("application/json", JSON.stringify(field));
      }}
    >
      <div className="flex items-center gap-2.5 truncate">
        {icon}
        <span className="truncate">{field.label}</span>
      </div>
      {!isSelected && <Plus className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 text-[color:var(--text-muted)]" />}
    </div>
  );
}

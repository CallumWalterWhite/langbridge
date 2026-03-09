'use client';

import { JSX } from 'react';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import type { ConnectorConfigEntry } from '@/orchestration/connectors';

type ConnectorConfigFieldsProps = {
  entries: ConnectorConfigEntry[];
  values: Record<string, string>;
  onChange: (field: string, value: string) => void;
};

function renderConfigInput(
  entry: ConnectorConfigEntry,
  value: string,
  onChange: (field: string, value: string) => void,
): JSX.Element {
  if (entry.valueList && entry.valueList.length > 0) {
    return (
      <Select
        id={`config-${entry.field}`}
        placeholder={`Select ${entry.label ?? entry.field}`}
        value={value}
        onChange={(event) => onChange(entry.field, event.target.value)}
      >
        {entry.valueList.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </Select>
    );
  }

  if (entry.type === 'password') {
    return (
      <Input
        id={`config-${entry.field}`}
        type="password"
        autoComplete="off"
        value={value}
        onChange={(event) => onChange(entry.field, event.target.value)}
      />
    );
  }

  if (entry.type === 'number') {
    return (
      <Input
        id={`config-${entry.field}`}
        type="number"
        value={value}
        onChange={(event) => onChange(entry.field, event.target.value)}
      />
    );
  }

  if (entry.type === 'boolean') {
    return (
      <Select
        id={`config-${entry.field}`}
        placeholder={`Select ${entry.label ?? entry.field}`}
        value={value || ''}
        onChange={(event) => onChange(entry.field, event.target.value)}
      >
        <option value="true">True</option>
        <option value="false">False</option>
      </Select>
    );
  }

  if (entry.type === 'textarea') {
    return (
      <Textarea
        id={`config-${entry.field}`}
        value={value}
        onChange={(event) => onChange(entry.field, event.target.value)}
      />
    );
  }

  return (
    <Input
      id={`config-${entry.field}`}
      value={value}
      onChange={(event) => onChange(entry.field, event.target.value)}
    />
  );
}

export function ConnectorConfigFields({
  entries,
  values,
  onChange,
}: ConnectorConfigFieldsProps): JSX.Element {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {entries.map((entry) => {
        const value = values[entry.field] ?? '';
        return (
          <div key={entry.field} className="space-y-2">
            <Label
              htmlFor={`config-${entry.field}`}
              className="flex items-center gap-2 text-[color:var(--text-secondary)]"
            >
              <span>{entry.label ?? entry.field}</span>
              {entry.required ? (
                <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">
                  Required
                </span>
              ) : null}
            </Label>
            {renderConfigInput(entry, value, onChange)}
            {entry.description ? (
              <p className="text-xs text-[color:var(--text-muted)]">{entry.description}</p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

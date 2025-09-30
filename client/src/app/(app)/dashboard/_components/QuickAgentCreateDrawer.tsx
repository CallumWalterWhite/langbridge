'use client';

import * as React from 'react';
import { useMutation } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Drawer, DrawerClose, DrawerContent } from '@/components/ui/drawer';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';

import type { DataSource } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

function withApiBase(path: string) {
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE}${path}`;
}

const TEMPLATE_OPTIONS = [
  { value: 'sql_analyst', label: 'SQL Analyst (NL->SQL)' },
  { value: 'docs_qa', label: 'Docs Q&A (RAG)' },
  { value: 'hybrid', label: 'Hybrid (SQL + RAG)' },
] as const;

type TemplateValue = (typeof TEMPLATE_OPTIONS)[number]['value'];

type AgentPayload = {
  name: string;
  kind: TemplateValue;
  sourceIds: string[];
};

export interface QuickAgentCreateDrawerProps {
  sources: DataSource[];
  onCreated?: (agentId: string) => void;
}

export function QuickAgentCreateDrawer({ sources, onCreated }: QuickAgentCreateDrawerProps) {
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const [template, setTemplate] = React.useState<TemplateValue | ''>('');
  const [name, setName] = React.useState('');
  const [selectedSources, setSelectedSources] = React.useState<string[]>([]);
  const [formError, setFormError] = React.useState<string | null>(null);

  const resetState = React.useCallback(() => {
    setName('');
    setSelectedSources([]);
    setFormError(null);
  }, []);

  React.useEffect(() => {
    if (!open) {
      resetState();
      setTemplate('');
    }
  }, [open, resetState]);

  const handleTemplateChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value as TemplateValue | '';
    if (!value) {
      setTemplate('');
      setOpen(false);
      return;
    }
    setTemplate(value);
    setOpen(true);
  };

  const toggleSource = (sourceId: string) => () => {
    setSelectedSources((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId],
    );
  };

  const mutation = useMutation<{ id: string }, Error, AgentPayload>({
    mutationFn: async (payload) => {
      const response = await fetch(withApiBase('/api/v1/agents'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || 'Failed to create agent');
      }
      return response.json() as Promise<{ id: string }>;
    },
    onSuccess: ({ id }) => {
      toast({ title: 'Agent created', description: 'Your agent is now ready.' });
      onCreated?.(id);
      setOpen(false);
    },
    onError: (error) => {
      toast({ title: 'Unable to create agent', description: error.message, variant: 'destructive' });
      setFormError(error.message);
    },
  });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!template) {
      setFormError('Select a template to continue.');
      return;
    }
    if (!name.trim()) {
      setFormError('Agent name is required.');
      return;
    }

    const payload: AgentPayload = {
      name: name.trim(),
      kind: template,
      sourceIds: selectedSources,
    };

    mutation.mutate(payload);
  };

  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="agent-template">Quick create</Label>
        <Select
          id="agent-template"
          value={template}
          onChange={handleTemplateChange}
          placeholder="Choose a template"
          aria-describedby="agent-template-description"
        >
          {TEMPLATE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        <p id="agent-template-description" className="mt-2 text-xs text-slate-500">
          Spin up a ready-to-use agent with recommended defaults.
        </p>
      </div>

      <Drawer open={open} onOpenChange={setOpen}>
        <DrawerContent>
          <form onSubmit={handleSubmit} className="flex h-full flex-col gap-6">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold">Create agent</h2>
              <p className="text-sm text-slate-500">
                Template: {template ? TEMPLATE_OPTIONS.find((item) => item.value === template)?.label : 'Select template'}
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="agent-name">Agent name</Label>
                <Input id="agent-name" placeholder="Growth insights" value={name} onChange={(event) => setName(event.target.value)} required />
              </div>

              <div>
                <Label>Connect sources</Label>
                <div className="mt-2 space-y-2">
                  {sources.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500">
                      No sources available yet. Add a source to link it here.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {sources.map((source) => {
                        const id = `source-${source.id}`;
                        const checked = selectedSources.includes(source.id);
                        return (
                          <li key={source.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2">
                            <label htmlFor={id} className="flex flex-1 cursor-pointer items-center justify-between gap-3 text-sm">
                              <span>
                                <span className="font-medium text-slate-900">{source.name}</span>
                                <span className="ml-2 text-xs uppercase text-slate-400">{source.type}</span>
                              </span>
                              <input
                                id={id}
                                type="checkbox"
                                checked={checked}
                                onChange={toggleSource(source.id)}
                                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                              />
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </div>
            </div>

            {formError ? <p className="text-sm text-red-600" role="alert">{formError}</p> : null}

            <div className="mt-auto flex flex-col gap-2 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end">
              <DrawerClose>
                <Button type="button" variant="ghost">
                  Cancel
                </Button>
              </DrawerClose>
              <Button type="submit" isLoading={mutation.isPending} loadingText="Creating...">
                Create agent
              </Button>
            </div>
          </form>
        </DrawerContent>
      </Drawer>
    </div>
  );
}

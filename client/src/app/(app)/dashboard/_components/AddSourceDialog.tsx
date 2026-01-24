'use client';

import * as React from 'react';
import { useMutation } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';

import type { DataSource } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

function withApiBase(path: string) {
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE}${path}`;
}

const DATABASE_OPTIONS = [
  { value: 'snowflake', label: 'Snowflake' },
  { value: 'postgres', label: 'Postgres' },
  { value: 'mysql', label: 'MySQL' },
] as const;

type DatabaseType = (typeof DATABASE_OPTIONS)[number]['value'];

const API_AUTH_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'api_key', label: 'API Key' },
  { value: 'bearer', label: 'Bearer' },
] as const;

type ApiAuthType = (typeof API_AUTH_TYPES)[number]['value'];

export interface AddSourceDialogProps {
  children: React.ReactElement;
  organizationId?: string;
  onCreated?: (source: DataSource | { id: string }) => void;
}

export function AddSourceDialog({ children, organizationId, onCreated }: AddSourceDialogProps) {
  const [open, setOpen] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState<'databases' | 'apis'>('databases');
  const { toast } = useToast();

  const [databaseForm, setDatabaseForm] = React.useState({
    name: '',
    type: 'snowflake' as DatabaseType,
    host: '',
    port: '',
    database: '',
    username: '',
    password: '',
    warehouse: '',
    account: '',
    extraParams: '',
  });

  const [apiForm, setApiForm] = React.useState({
    name: '',
    baseUrl: '',
    authType: 'none' as ApiAuthType,
    apiKey: '',
    bearerToken: '',
  });

  const [formError, setFormError] = React.useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      if (!organizationId) {
        throw new Error('Select an organization before adding a source.');
      }
      const response = await fetch(withApiBase(`/api/v1/datasources/${organizationId}`), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || 'Failed to create data source');
      }
      return response.json() as Promise<{ id: string } | DataSource>;
    },
    onSuccess: (result) => {
      toast({ title: 'Source added', description: 'Your data source is ready to use.' });
      onCreated?.(result);
      setOpen(false);
      resetForms();
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to create data source';
      toast({ title: 'Unable to save source', description: message, variant: 'destructive' });
      setFormError(message);
    },
  });

  const resetForms = React.useCallback(() => {
    setDatabaseForm({
      name: '',
      type: 'snowflake',
      host: '',
      port: '',
      database: '',
      username: '',
      password: '',
      warehouse: '',
      account: '',
      extraParams: '',
    });
    setApiForm({ name: '', baseUrl: '', authType: 'none', apiKey: '', bearerToken: '' });
    setActiveTab('databases');
    setFormError(null);
  }, []);

  React.useEffect(() => {
    if (!open) {
      resetForms();
    }
  }, [open, resetForms]);

  const handleDatabaseChange = (field: keyof typeof databaseForm) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      const value = event.target.value;
      setDatabaseForm((prev) => ({ ...prev, [field]: value }));
    };

  const handleApiChange = (field: keyof typeof apiForm) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const value = event.target.value;
      setApiForm((prev) => ({ ...prev, [field]: value }));
    };

  const validateDatabaseForm = () => {
    const requiredFields: Array<keyof typeof databaseForm> = ['name', 'host', 'port', 'database', 'username', 'password'];
    for (const field of requiredFields) {
      if (!databaseForm[field].trim()) {
        return `${field.charAt(0).toUpperCase()}${field.slice(1)} is required`;
      }
    }
    if (databaseForm.type === 'snowflake') {
      if (!databaseForm.warehouse.trim()) {
        return 'Warehouse is required for Snowflake';
      }
      if (!databaseForm.account.trim()) {
        return 'Account is required for Snowflake';
      }
    }
    if (databaseForm.port && Number.isNaN(Number(databaseForm.port))) {
      return 'Port must be a number';
    }
    if (databaseForm.extraParams) {
      try {
        JSON.parse(databaseForm.extraParams);
      } catch {
        return 'Extra params must be valid JSON';
      }
    }
    return null;
  };

  const validateApiForm = () => {
    if (!apiForm.name.trim()) {
      return 'Name is required';
    }
    if (!apiForm.baseUrl.trim()) {
      return 'Base URL is required';
    }
    if (apiForm.authType === 'api_key' && !apiForm.apiKey.trim()) {
      return 'API key is required';
    }
    if (apiForm.authType === 'bearer' && !apiForm.bearerToken.trim()) {
      return 'Bearer token is required';
    }
    return null;
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (activeTab === 'databases') {
      const validation = validateDatabaseForm();
      if (validation) {
        setFormError(validation);
        return;
      }
      const payload: Record<string, unknown> = {
        name: databaseForm.name.trim(),
        type: databaseForm.type,
        config: {
          host: databaseForm.host.trim(),
          port: Number(databaseForm.port) || undefined,
          database: databaseForm.database.trim(),
          username: databaseForm.username.trim(),
          password: databaseForm.password,
          warehouse: databaseForm.type === 'snowflake' ? databaseForm.warehouse.trim() : undefined,
          account: databaseForm.type === 'snowflake' ? databaseForm.account.trim() : undefined,
          extraParams: databaseForm.extraParams ? JSON.parse(databaseForm.extraParams) : undefined,
        },
      };
      mutation.mutate(payload);
      return;
    }

    const validation = validateApiForm();
    if (validation) {
      setFormError(validation);
      return;
    }

    const payload: Record<string, unknown> = {
      name: apiForm.name.trim(),
      type: 'api',
      config: {
        baseUrl: apiForm.baseUrl.trim(),
        authType: apiForm.authType,
        apiKey: apiForm.authType === 'api_key' ? apiForm.apiKey.trim() : undefined,
        bearerToken: apiForm.authType === 'bearer' ? apiForm.bearerToken.trim() : undefined,
      },
    };
    mutation.mutate(payload);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger>{children}</DialogTrigger>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Add Source</DialogTitle>
          <DialogDescription>
            Configure your connection details. Credentials are encrypted and stored securely.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-8">
          <Tabs defaultValue="databases" value={activeTab} onValueChange={(value) => setActiveTab(value as 'databases' | 'apis')}>
            <TabsList>
              <TabsTrigger value="databases">Databases</TabsTrigger>
              <TabsTrigger value="apis">APIs</TabsTrigger>
            </TabsList>
            <TabsContent value="databases">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <Label htmlFor="db-name">Connection name</Label>
                  <Input id="db-name" placeholder="Finance warehouse" value={databaseForm.name} onChange={handleDatabaseChange('name')} required />
                </div>
                <div>
                  <Label htmlFor="db-type">Type</Label>
                  <Select id="db-type" value={databaseForm.type} onChange={handleDatabaseChange('type')}>
                    {DATABASE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label htmlFor="db-host">Host</Label>
                  <Input id="db-host" placeholder="my-db.example.com" value={databaseForm.host} onChange={handleDatabaseChange('host')} required />
                </div>
                <div>
                  <Label htmlFor="db-port">Port</Label>
                  <Input id="db-port" placeholder="5432" value={databaseForm.port} onChange={handleDatabaseChange('port')} required />
                </div>
                <div>
                  <Label htmlFor="db-database">Database</Label>
                  <Input id="db-database" placeholder="analytics" value={databaseForm.database} onChange={handleDatabaseChange('database')} required />
                </div>
                <div>
                  <Label htmlFor="db-username">Username</Label>
                  <Input id="db-username" placeholder="db_admin" value={databaseForm.username} onChange={handleDatabaseChange('username')} required autoComplete="username" />
                </div>
                <div>
                  <Label htmlFor="db-password">Password</Label>
                  <Input
                    id="db-password"
                    type="password"
                    placeholder="********"
                    value={databaseForm.password}
                    onChange={handleDatabaseChange('password')}
                    required
                    autoComplete="current-password"
                  />
                </div>
                {databaseForm.type === 'snowflake' ? (
                  <>
                    <div>
                      <Label htmlFor="db-warehouse">Warehouse</Label>
                      <Input id="db-warehouse" placeholder="COMPUTE_WH" value={databaseForm.warehouse} onChange={handleDatabaseChange('warehouse')} required />
                    </div>
                    <div>
                      <Label htmlFor="db-account">Account</Label>
                      <Input id="db-account" placeholder="xy12345.us-east-1" value={databaseForm.account} onChange={handleDatabaseChange('account')} required />
                    </div>
                  </>
                ) : null}
                <div className="md:col-span-2">
                  <Label htmlFor="db-extra">Extra params JSON (optional)</Label>
                  <Textarea id="db-extra" placeholder='{"schema":"public"}' value={databaseForm.extraParams} onChange={handleDatabaseChange('extraParams')} rows={4} />
                </div>
              </div>
            </TabsContent>
            <TabsContent value="apis">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <Label htmlFor="api-name">API name</Label>
                  <Input id="api-name" placeholder="Salesforce API" value={apiForm.name} onChange={handleApiChange('name')} required />
                </div>
                <div className="md:col-span-2">
                  <Label htmlFor="api-base-url">Base URL</Label>
                  <Input id="api-base-url" placeholder="https://api.example.com" value={apiForm.baseUrl} onChange={handleApiChange('baseUrl')} required />
                </div>
                <div>
                  <Label htmlFor="api-auth-type">Auth type</Label>
                  <Select id="api-auth-type" value={apiForm.authType} onChange={handleApiChange('authType')}>
                    {API_AUTH_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
                {apiForm.authType === 'api_key' ? (
                  <div className="md:col-span-2">
                    <Label htmlFor="api-key">API key</Label>
                    <Input id="api-key" placeholder="Enter API key" value={apiForm.apiKey} onChange={handleApiChange('apiKey')} required />
                  </div>
                ) : null}
                {apiForm.authType === 'bearer' ? (
                  <div className="md:col-span-2">
                    <Label htmlFor="api-bearer">Bearer token</Label>
                    <Input id="api-bearer" placeholder="Enter bearer token" value={apiForm.bearerToken} onChange={handleApiChange('bearerToken')} required />
                  </div>
                ) : null}
              </div>
            </TabsContent>
          </Tabs>

          {formError ? <p className="text-sm text-red-600" role="alert">{formError}</p> : null}

          <DialogFooter>
            <DialogClose>
              <Button type="button" variant="ghost">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" isLoading={mutation.isPending} loadingText="Saving...">
              Save source
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}





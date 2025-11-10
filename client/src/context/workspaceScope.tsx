'use client';

import {
  createContext,
  JSX,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { fetchOrganizations, type Organization, type Project } from '@/orchestration/organizations';

interface WorkspaceScopeContextValue {
  organizations: Organization[];
  loading: boolean;
  error: string | null;
  selectedOrganizationId: string;
  selectedProjectId: string;
  selectedOrganization: Organization | null;
  selectedProject: Project | null;
  setSelectedOrganizationId: (organizationId: string) => void;
  setSelectedProjectId: (projectId: string) => void;
  refreshOrganizations: () => Promise<void>;
}

const WorkspaceScopeContext = createContext<WorkspaceScopeContextValue | undefined>(undefined);

const ORGANIZATION_STORAGE_KEY = 'langbridge:selectedOrganizationId';
const PROJECT_STORAGE_KEY = 'langbridge:selectedProjectId';

function withBrowserStorage(action: (storage: Storage) => void) {
  if (typeof window === 'undefined') {
    return;
  }
  action(window.localStorage);
}

function resolveInitialValue(key: string): string {
  if (typeof window === 'undefined') {
    return '';
  }
  try {
    return window.localStorage.getItem(key) ?? '';
  } catch {
    return '';
  }
}

export function WorkspaceScopeProvider({ children }: { children: ReactNode }): JSX.Element {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedOrganizationId, setSelectedOrganizationIdState] = useState<string>(() =>
    resolveInitialValue(ORGANIZATION_STORAGE_KEY),
  );
  const [selectedProjectId, setSelectedProjectIdState] = useState<string>(() =>
    resolveInitialValue(PROJECT_STORAGE_KEY),
  );

  const isMounted = useRef(false);

  const refreshOrganizations = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchOrganizations();
      setOrganizations(data);
      setError(null);
    } catch (refreshError) {
      const message =
        refreshError instanceof Error ? refreshError.message : 'Unable to load organizations right now.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    isMounted.current = true;
    void refreshOrganizations();
    return () => {
      isMounted.current = false;
    };
  }, [refreshOrganizations]);

  const ensureProjectSelection = useCallback(
    (organizationId: string, currentProjectId: string): string => {
      if (!organizationId) {
        return '';
      }
      const organization = organizations.find((item) => item.id === organizationId);
      if (!organization) {
        return '';
      }
      if (!currentProjectId) {
        return '';
      }
      const projectExists = organization.projects.some((project) => project.id === currentProjectId);
      return projectExists ? currentProjectId : '';
    },
    [organizations],
  );

  const setSelectedOrganizationId = useCallback(
    (organizationId: string) => {
      setSelectedOrganizationIdState(organizationId);
      withBrowserStorage((storage) => {
        if (organizationId) {
          storage.setItem(ORGANIZATION_STORAGE_KEY, organizationId);
        } else {
          storage.removeItem(ORGANIZATION_STORAGE_KEY);
        }
      });
      setSelectedProjectIdState((currentProjectId) => {
        const nextProjectId = ensureProjectSelection(organizationId, currentProjectId);
        withBrowserStorage((storage) => {
          if (nextProjectId) {
            storage.setItem(PROJECT_STORAGE_KEY, nextProjectId);
          } else {
            storage.removeItem(PROJECT_STORAGE_KEY);
          }
        });
        return nextProjectId;
      });
    },
    [ensureProjectSelection],
  );

  const setSelectedProjectId = useCallback((projectId: string) => {
    setSelectedProjectIdState(projectId);
    withBrowserStorage((storage) => {
      if (projectId) {
        storage.setItem(PROJECT_STORAGE_KEY, projectId);
      } else {
        storage.removeItem(PROJECT_STORAGE_KEY);
      }
    });
  }, []);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (organizations.length === 0) {
      if (selectedOrganizationId) {
        setSelectedOrganizationId('');
      }
      if (selectedProjectId) {
        setSelectedProjectId('');
      }
      return;
    }

    const organizationExists = organizations.some((item) => item.id === selectedOrganizationId);
    if (!organizationExists) {
      setSelectedOrganizationId(organizations[0]?.id ?? '');
      return;
    }

    const nextProjectId = ensureProjectSelection(selectedOrganizationId, selectedProjectId);
    if (nextProjectId !== selectedProjectId) {
      setSelectedProjectId(nextProjectId);
    }
  }, [
    loading,
    organizations,
    selectedOrganizationId,
    selectedProjectId,
    ensureProjectSelection,
    setSelectedOrganizationId,
    setSelectedProjectId,
  ]);

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === selectedOrganizationId) ?? null,
    [organizations, selectedOrganizationId],
  );

  const selectedProject = useMemo(() => {
    if (!selectedOrganization) {
      return null;
    }
    return selectedOrganization.projects.find((project) => project.id === selectedProjectId) ?? null;
  }, [selectedOrganization, selectedProjectId]);

  const value = useMemo<WorkspaceScopeContextValue>(
    () => ({
      organizations,
      loading,
      error,
      selectedOrganizationId,
      selectedProjectId,
      selectedOrganization,
      selectedProject,
      setSelectedOrganizationId,
      setSelectedProjectId,
      refreshOrganizations,
    }),
    [
      organizations,
      loading,
      error,
      selectedOrganizationId,
      selectedProjectId,
      selectedOrganization,
      selectedProject,
      setSelectedOrganizationId,
      setSelectedProjectId,
      refreshOrganizations,
    ],
  );

  return <WorkspaceScopeContext.Provider value={value}>{children}</WorkspaceScopeContext.Provider>;
}

export function useWorkspaceScope(): WorkspaceScopeContextValue {
  const context = useContext(WorkspaceScopeContext);
  if (!context) {
    throw new Error('useWorkspaceScope must be used within a WorkspaceScopeProvider');
  }
  return context;
}

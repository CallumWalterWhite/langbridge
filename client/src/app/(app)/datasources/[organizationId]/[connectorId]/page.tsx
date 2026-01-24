'use client';

import { useEffect } from 'react';

import { useWorkspaceScope } from '@/context/workspaceScope';
import { ConnectorUpdate } from '../../[connectorId]/_components/ConnectorUpdate';

type ConnectorPageProps = {
  params: { connectorId: string; organizationId: string };
};

export default function ConnectorPage({ params }: ConnectorPageProps) {
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  return <ConnectorUpdate organizationId={organizationId} connectorId={params.connectorId} />;
}

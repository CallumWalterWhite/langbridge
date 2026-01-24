'use client';

import { useEffect } from 'react';

import { useWorkspaceScope } from '@/context/workspaceScope';
import { ChatInterface } from '../../[threadId]/_components/ChatInterface';

type ChatThreadPageProps = {
  params: { threadId: string; organizationId: string };
};

export default function ChatThreadPage({ params }: ChatThreadPageProps) {
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  return <ChatInterface organizationId={organizationId} threadId={params.threadId} />;
}

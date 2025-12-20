'use client';

import { JSX } from 'react';
import { useRouter } from 'next/navigation';

import { AgentDefinitionForm } from '../components/agent-definition-form';

export default function CreateAgentDefinitionPage(): JSX.Element {
  const router = useRouter();

  return (
    <AgentDefinitionForm
      mode="create"
      onComplete={() => {
        router.push('/agents/definitions');
      }}
    />
  );
}

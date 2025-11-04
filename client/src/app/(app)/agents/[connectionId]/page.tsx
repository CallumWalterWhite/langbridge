'use client';

import { LLMConnectionUpdate } from './_components/LLMConnectionUpdate';

type LLMConnectionPageProps = {
  params: { connectionId: string };
};

export default function LLMConnectionPage({ params }: LLMConnectionPageProps): JSX.Element {
  const numericId = Number(params.connectionId);

  if (!Number.isFinite(numericId)) {
    return (
      <div className="text-sm text-[color:var(--text-muted)]">
        Invalid connection identifier. Return to the list and select a valid connection.
      </div>
    );
  }

  return <LLMConnectionUpdate connectionId={numericId} />;
}

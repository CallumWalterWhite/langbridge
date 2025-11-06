'use client';

import { JSX } from 'react';
import { LLMConnectionUpdate } from './_components/LLMConnectionUpdate';

type LLMConnectionPageProps = {
  params: { connectionId: string };
};

export default function LLMConnectionPage({ params }: LLMConnectionPageProps): JSX.Element {
  return <LLMConnectionUpdate connectionId={params.connectionId} />;
}

'use client';

import { ConnectorUpdate } from './_components/ConnectorUpdate';

type ConnectorPageProps = {
  params: { connectorId: string };
};

export default function ConnectorPage({ params }: ConnectorPageProps) {
  return <ConnectorUpdate connectorId={params.connectorId} />;
}

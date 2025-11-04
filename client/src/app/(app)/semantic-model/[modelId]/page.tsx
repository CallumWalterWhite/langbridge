'use client';

import { SemanticModelDetail } from './_components/SemanticModelDetail';

type SemanticModelPageProps = {
  params: { modelId: string };
};

export default function SemanticModelPage({ params }: SemanticModelPageProps): JSX.Element {
  return <SemanticModelDetail modelId={params.modelId} />;
}

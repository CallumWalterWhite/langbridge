import PageClient from './page-client';

export const dynamic = 'force-dynamic';

export default function Page() {
  const backendUrl = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

  return <PageClient backendUrl={backendUrl} />;
}

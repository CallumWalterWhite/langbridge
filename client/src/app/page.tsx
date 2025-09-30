'use client';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL!;

export default function Page() {
  const loginUrl = `${BACKEND}/api/v1/auth/login/github`;
  return (
    <main style={{ display: 'grid', placeItems: 'center', height: '100dvh' }}>
      <div style={{ padding: 24, borderRadius: 16, boxShadow: '0 10px 30px rgba(0,0,0,0.08)' }}>
        <h1>Sign in</h1>
        <p>Use your GitHub account to continue.</p>
        <a href={loginUrl} style={{
          display: 'inline-block',
          padding: '10px 16px',
          borderRadius: 10,
          border: '1px solid #ccc',
          textDecoration: 'none'
        }}>Sign in with GitHub</a>
      </div>
    </main>
  );
}
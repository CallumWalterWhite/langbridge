import { ChatInterface } from './_components/ChatInterface';

type ChatSessionPageProps = {
  params: { sessionId: string };
};

export default function ChatSessionPage({ params }: ChatSessionPageProps) {
  return <ChatInterface sessionId={params.sessionId} />;
}

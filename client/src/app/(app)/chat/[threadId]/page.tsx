import { ChatInterface } from './_components/ChatInterface';

type ChatThreadPageProps = {
  params: { threadId: string };
};

export default function ChatThreadPage({ params }: ChatThreadPageProps) {
  return <ChatInterface threadId={params.threadId} />;
}

export type ChatSession = {
  id: string;
  createdAt: string;
};

export type ChatSessionResponse = {
  sessionId: string;
};

export type ChatMessage = {
  id: string;
  sessionId: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  createdAt: string;
};

export type ChatMessagePair = {
  user: ChatMessage;
  assistant: ChatMessage;
};

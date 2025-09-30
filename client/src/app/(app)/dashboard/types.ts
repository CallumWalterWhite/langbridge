export type DataSource = {
  id: string;
  name: string;
  type: 'snowflake' | 'postgres' | 'mysql' | 'api';
  status: 'connected' | 'error' | 'pending';
  createdAt: string;
};

export type Agent = {
  id: string;
  name: string;
  kind: 'sql_analyst' | 'docs_qa' | 'hybrid';
  sourceIds: string[];
  createdAt: string;
};

export type CreateChatResponse = {
  sessionId: string;
};

import { Sparkles, Command } from 'lucide-react';
import { Button } from '@/components/ui/button';

type CopilotAgentOption = {
  id: string;
  name: string;
  description?: string | null;
};

type BiAiInputProps = {
  agents: CopilotAgentOption[];
  selectedAgentId: string;
  onSelectAgent: (agentId: string) => void;
  prompt: string;
  onPromptChange: (value: string) => void;
  onSubmit: () => void;
  isRunning?: boolean;
  statusMessage?: string | null;
  summary?: string | null;
};

export function BiAiInput({
  agents,
  selectedAgentId,
  onSelectAgent,
  prompt,
  onPromptChange,
  onSubmit,
  isRunning = false,
  statusMessage,
  summary,
}: BiAiInputProps) {
  const canSubmit = Boolean(prompt.trim()) && Boolean(selectedAgentId) && !isRunning;

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[100] w-full max-w-xl px-4">
      {summary ? (
        <div className="mb-2 rounded-2xl border border-primary/20 bg-background/85 px-4 py-3 text-xs text-muted-foreground shadow-[0_14px_36px_rgba(var(--primary-rgb),0.16)] backdrop-blur-xl">
          {summary}
        </div>
      ) : null}
      <div className="backdrop-blur-xl bg-background/70 border border-primary/20 shadow-[0_20px_50px_rgba(var(--primary-rgb),0.15)] rounded-2xl p-1.5 flex items-center gap-2 group focus-within:ring-2 ring-primary/20 transition-all duration-500">
        <div className="flex-1 flex items-center gap-3 px-3 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary to-violet-500 flex items-center justify-center text-white shrink-0 shadow-lg shadow-primary/20">
            <Sparkles className="h-4 w-4 fill-white" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex items-center gap-2">
              <select
                className="h-7 max-w-[14rem] rounded-lg border border-primary/20 bg-background/80 px-2 text-[11px] text-foreground focus:outline-none"
                value={selectedAgentId}
                onChange={(event) => onSelectAgent(event.target.value)}
              >
                {agents.length === 0 ? (
                  <option value="">No copilot agents available</option>
                ) : null}
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
              {statusMessage ? (
                <span className="truncate text-[11px] text-muted-foreground">{statusMessage}</span>
              ) : null}
            </div>
            <input
              className="w-full bg-transparent border-none focus:outline-none text-sm placeholder:text-muted-foreground text-foreground py-1.5"
              placeholder="Ask AI to build a KPI dashboard with filters..."
              type="text"
              value={prompt}
              onChange={(event) => onPromptChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && canSubmit) {
                  event.preventDefault();
                  onSubmit();
                }
              }}
            />
          </div>
        </div>
        <div className="flex items-center gap-1 pr-1">
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 bg-muted/50 rounded-lg text-[10px] font-bold text-muted-foreground uppercase tracking-widest mr-1">
            <Command className="h-3 w-3" /> K
          </div>
          <Button
            size="sm"
            className="h-9 px-4 rounded-xl bg-gradient-to-r from-primary to-violet-500 text-white border-0 text-xs font-bold uppercase tracking-wider hover:opacity-90 transition-opacity shadow-sm"
            disabled={!canSubmit}
            onClick={onSubmit}
          >
            {isRunning ? 'Running' : 'Generate'}
          </Button>
        </div>
      </div>
    </div>
  );
}

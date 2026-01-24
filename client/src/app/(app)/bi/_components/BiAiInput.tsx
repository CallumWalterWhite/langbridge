import { Sparkles, Command } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function BiAiInput() {
  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[100] w-full max-w-xl px-4">
      <div className="backdrop-blur-xl bg-background/70 border border-primary/20 shadow-[0_20px_50px_rgba(var(--primary-rgb),0.15)] rounded-2xl p-1.5 flex items-center gap-2 group focus-within:ring-2 ring-primary/20 transition-all duration-500">
        <div className="flex-1 flex items-center gap-3 px-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary to-violet-500 flex items-center justify-center text-white shrink-0 shadow-lg shadow-primary/20">
            <Sparkles className="h-4 w-4 fill-white" />
          </div>
          <input 
            className="w-full bg-transparent border-none focus:outline-none text-sm placeholder:text-muted-foreground text-foreground py-2" 
            placeholder="Ask AI to 'Build a dashboard for Q3 sales'..." 
            type="text" 
          />
        </div>
        <div className="flex items-center gap-1 pr-1">
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 bg-muted/50 rounded-lg text-[10px] font-bold text-muted-foreground uppercase tracking-widest mr-1">
            <Command className="h-3 w-3" /> K
          </div>
          <Button 
            size="sm" 
            className="h-9 px-4 rounded-xl bg-gradient-to-r from-primary to-violet-500 text-white border-0 text-xs font-bold uppercase tracking-wider hover:opacity-90 transition-opacity shadow-sm"
          >
            Generate
          </Button>
        </div>
      </div>
    </div>
  );
}

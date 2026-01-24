export const metadata = {
  title: "What's New | LangBridge",
};

export default function WhatsNewPage() {
  return (
    <div className="max-w-4xl mx-auto py-10 px-6">
      <h1 className="text-4xl font-bold mb-2">What&apos;s New in LangBridge</h1>
      <p className="text-muted-foreground text-lg mb-8">
        Stay up to date with the latest features and improvements to the LangBridge platform.
      </p>

      <div className="space-y-12">
        <section>
          <div className="flex items-center gap-2 mb-4">
            <span className="bg-primary/10 text-primary text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              New Feature
            </span>
            <span className="text-sm text-muted-foreground">January 2026</span>
          </div>
          <h2 className="text-2xl font-semibold mb-3">Agent Orchestration Engine</h2>
          <p className="text-muted-foreground mb-4">
            We&apos;ve launched our core Agent Orchestration Engine, allowing you to coordinate multiple AI agents
            to perform complex, multi-step tasks. Agents can now share context and hand off sub-tasks seamlessly.
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-4">
            <li>Dynamic task routing based on agent capability</li>
            <li>Shared memory across agent sessions</li>
            <li>Human-in-the-loop approval workflows</li>
          </ul>
        </section>

        <section>
          <div className="flex items-center gap-2 mb-4">
            <span className="bg-primary/10 text-primary text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              Improvement
            </span>
            <span className="text-sm text-muted-foreground">January 2026</span>
          </div>
          <h2 className="text-2xl font-semibold mb-3">Semantic Model Versioning</h2>
          <p className="text-muted-foreground mb-4">
            Managing your data&apos;s semantic layer just got easier. You can now version your semantic models,
            enabling safe rollbacks and staging environments for your data definitions.
          </p>
        </section>

        <section>
          <div className="flex items-center gap-2 mb-4">
            <span className="bg-primary/10 text-primary text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              New Connector
            </span>
            <span className="text-sm text-muted-foreground">January 2026</span>
          </div>
          <h2 className="text-2xl font-semibold mb-3">Shopify & BigQuery Integration</h2>
          <p className="text-muted-foreground mb-4">
            Connect your e-commerce data directly to LangBridge. Our new Shopify connector allows agents
            to query orders, products, and customer data in real-time, while BigQuery support enables
            large-scale analytical queries.
          </p>
        </section>

        <section className="pt-6 border-t">
          <h3 className="text-xl font-semibold mb-2">Getting Started</h3>
          <p className="text-muted-foreground">
            New to LangBridge? Check out our <a href="/docs" className="text-primary hover:underline">documentation</a> to learn how to build your first agent workflow.
          </p>
        </section>
      </div>
    </div>
  );
}

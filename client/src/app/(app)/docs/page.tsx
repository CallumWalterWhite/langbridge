export const metadata = {
  title: 'Documentation | LangBridge',
};

export default function DocsPage() {
  const categories = [
    {
      title: 'Getting Started',
      description: 'Learn the basics of LangBridge and how to set up your first project.',
      links: [
        { name: 'Introduction', href: '/docs/introduction' },
        { name: 'Quick Start Guide', href: '/docs/quickstart' },
        { name: 'Architecture Overview', href: '/docs/architecture' },
      ],
    },
    {
      title: 'Agents',
      description: 'Define, train, and orchestrate intelligent agents.',
      links: [
        { name: 'Creating Agents', href: '/docs/agents/create' },
        { name: 'Agent Capabilities', href: '/docs/agents/capabilities' },
        { name: 'Orchestration Flows', href: '/docs/agents/orchestration' },
      ],
    },
    {
      title: 'Connectors',
      description: 'Connect LangBridge to your favorite data sources and tools.',
      links: [
        { name: 'Postgres Connector', href: '/docs/connectors/postgres' },
        { name: 'Shopify Connector', href: '/docs/connectors/shopify' },
        { name: 'Custom Connectors', href: '/docs/connectors/custom' },
      ],
    },
  ];

  return (
    <div className="max-w-5xl mx-auto py-12 px-6">
      <div className="mb-12">
        <h1 className="text-4xl font-bold mb-4">Documentation</h1>
        <p className="text-xl text-muted-foreground">
          Everything you need to build intelligent, data-driven agent workflows.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {categories.map((category) => (
          <div key={category.title} className="p-6 rounded-lg border bg-card text-card-foreground shadow-sm">
            <h2 className="text-2xl font-semibold mb-2">{category.title}</h2>
            <p className="text-muted-foreground mb-4">{category.description}</p>
            <ul className="space-y-2">
              {category.links.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-primary hover:underline">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

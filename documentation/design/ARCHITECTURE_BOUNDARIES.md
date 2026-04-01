# Architecture Boundaries

## Target shape

`my_grc` is being structured as a modular monolith with explicit bounded contexts so it can evolve toward microservices only when the operational cost is justified.

Current bounded contexts:

1. Governance and Control Library
   - frameworks
   - controls
   - unified controls
   - mappings
   - reference documents

2. Portfolio and Risk
   - organizations
   - business units
   - products and flavors
   - assets
   - risks
   - findings
   - action items

3. Evidence and Assurance
   - evidence plans
   - evidence items
   - questionnaires
   - assessments
   - schedules

4. Integrations and Connectors
   - AWS profile registry
   - Confluence connections
   - script modules
   - circuit breaker and idempotency runtime state

5. Platform Operations
   - feature flags
   - observability
   - lifecycle integrity
   - health checks
   - deployment readiness

## Anti-corruption layers

External systems must not leak their raw shapes directly into the core domain.

Rules:

- spreadsheet imports go through importer normalization
- AWS evidence collection goes through evidence plans and collector contracts
- Confluence publishing goes through the integration client and resilience layer
- external scripts go through manifest or binding contracts
- future Jira, ServiceNow, CMDB, scanner, and IdP connectors must follow the same pattern

## Why this matters

This gives us:

- clearer ownership boundaries
- safer evolution of the data model
- an extraction path for future services without redesigning the domain
- less coupling between UI, storage, and external systems

## Microservice guidance

Microservices are not the default today. The default is:

- one codebase
- one database
- clear module boundaries
- explicit contracts
- extracted services only when scale, team boundaries, or runtime isolation justify the cost

This keeps the stack boring and maintainable while still preparing for future decomposition.

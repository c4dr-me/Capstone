Production secrets guidance for Member 3

- Never commit secrets into the repository.
- Use one of: environment variables, a cloud secret manager (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault), or a vault (HashiCorp Vault).
- Required secrets/envs:
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
  - `RESOLVEONE_CONTEXT_SIGNING_KEY`, `RESOLVEONE_RECEIPT_SIGNING_KEY`
  - Any LLM provider keys (`GROQ_API_KEY`, `OPENROUTER_API_KEY`) if Member 2 uses LLMs
- Example (Linux):

```bash
export NEO4J_URI="neo4j+s://..."
export NEO4J_USER="prod_user"
export NEO4J_PASSWORD="<secret>"
export RESOLVEONE_CONTEXT_SIGNING_KEY="<secret>"
```

- For container deployments, mount secrets via platform-specific mechanisms (Kubernetes secret, AWS Secrets Manager CSI driver, etc.).
- Rotate signing keys and database credentials regularly; record rotation in the runbook.

---
name: docs-site
description: 'MkDocs documentation server location and usage. Use when: (1) creating documentation, (2) writing guides or technical docs, (3) asked to put docs somewhere, (4) referencing the docs server, (5) adding new doc pages.'
---

# Documentation Server

## Location
- **Server:** MkDocs Material on DGX Spark (mihai@192.168.68.73)
- **URL:** http://192.168.68.73:8000
- **Directory:** ~/workspace/docs-site/
- **Config:** ~/workspace/docs-site/mkdocs.yml
- **Docs root:** ~/workspace/docs-site/docs/
- **Service:** `systemctl --user restart mkdocs-opportunities`

## Structure
```
docs/
  index.md                     # Home page
  engineering/                 # Technical implementation guides
  ai-opportunities/            # Startup research & analysis
  physical-ai/                 # Physical AI research
  agent-frameworks/            # Agent framework comparisons
  validation/                  # Market validation & competitive intel
  customer-discovery/          # Interview prep & discovery
  blog/                        # Blog posts
```

## How to Add a New Page

1. Write the markdown file and save it to the appropriate subdirectory under `~/workspace/docs-site/docs/`
2. Add a nav entry in `~/workspace/docs-site/mkdocs.yml` under the correct section
3. The server auto-reloads — the page appears immediately at http://192.168.68.73:8000/

## Conventions
- Use Material theme features: admonitions, tabs, code blocks with syntax highlighting
- Include a TL;DR at the top of long docs
- Link to external references (papers, repos, PRs) with full URLs
- Engineering docs go in `docs/engineering/`
- Use lowercase-kebab-case for filenames

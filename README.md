# CARTO Agent Skills

Skills for the Claude Code plugin marketplace that enable AI agents to manage CARTO Geospatial Cloud resources and analyze platform activity.

## Quick Start

```bash
# Add the marketplace (one time)
/plugin marketplace add CartoDB/carto-agent-skills

# Install skills
/plugin install carto-cli@carto-agent-skills
/plugin install carto-activity@carto-agent-skills
```

## Available Skills

### CARTO CLI

**Plugin ID**: `carto-cli@carto-agent-skills`

Manage CARTO Geospatial Cloud resources via CLI: maps, workflows, connections, authentication, and admin operations.

| File | Description |
|------|-------------|
| [`SKILL.md`](carto-cli/SKILL.md) | Main skill: overview, authentication, quick reference, and index |
| [`commands.md`](carto-cli/commands.md) | Complete command reference with all options and examples |
| [`maps.md`](carto-cli/maps.md) | Map JSON structure for create/update operations |

### CARTO Activity

**Plugin ID**: `carto-activity@carto-agent-skills`

Query CARTO activity logs and usage data with SQL for analyzing user behavior, map changes, API usage, and quota monitoring.

| File | Description |
|------|-------------|
| [`SKILL.md`](carto-activity/SKILL.md) | Activity data querying, SQL examples, and troubleshooting |

## What is the CARTO CLI?

The [CARTO CLI](https://docs.carto.com/carto-user-manual/carto-cli) is a command-line tool that enables direct interaction with CARTO from your terminal. With it, you can:

- Find and manage Maps, Workflows, connections, and developer credentials
- Move Maps and Workflows across different organizations
- Monitor organizational quotas and activity
- Work with existing AI Agents
- Share assets between team members

Install via npm:

```bash
npm install -g @carto/carto-cli
```

## Learn More

- [CARTO CLI Documentation](https://docs.carto.com/carto-user-manual/carto-cli)
- [CARTO Platform Documentation](https://docs.carto.com/)
- [CARTO CLI on npm](https://www.npmjs.com/package/@carto/carto-cli)

## Contributing

To update or improve these skills, submit a pull request with your changes. Ensure that:

- Documentation is clear and accurate
- Examples are tested and working
- Markdown formatting is consistent

# CARTO Agent Skills

This repository contains AI agent skills for interacting with the CARTO CLI.

## About

These skills enable AI agents (like Claude) to help you manage CARTO Geospatial Cloud resources via the command-line interface. The skills provide structured knowledge about CARTO CLI commands, map creation, workflow management, and more.

## What is the CARTO CLI?

The [CARTO CLI](https://docs.carto.com/carto-user-manual/carto-cli) is a command-line tool that enables direct interaction with CARTO from your terminal. With it, you can:

- Find and manage Maps, Workflows, connections, and developer credentials
- Move Maps and Workflows across different organizations
- Monitor organizational quotas and activity
- Work with existing AI Agents
- Share assets between team members

## Installation

Install the CARTO CLI via npm:

```bash
npm install -g @carto/carto-cli
```

For detailed installation and usage instructions, see the [official npm package documentation](https://www.npmjs.com/package/@carto/carto-cli).

## Skills Included

### carto-cli
Main skill for managing CARTO Geospatial Cloud resources via CLI. Covers authentication, maps, workflows, connections, credentials, and admin operations. Includes reference documents for the complete command syntax (`COMMANDS.md`) and map JSON structure (`MAPS.md`).

### carto-activity
Skill for querying and analyzing CARTO activity logs and usage data with SQL.

### carto-migration
Skill for migrating maps, workflows, and AI agent configurations between organizations, profiles, and users. Covers connection mapping, bulk migration, and post-migration validation.

## Usage with AI Agents

These skills serve as context for AI agents to understand how to use the CARTO CLI effectively. When loaded, the agent can:

- Help construct valid CLI commands
- Generate map JSON configurations
- Troubleshoot authentication issues
- Query and analyze activity data
- Migrate resources across organizations
- Manage CARTO resources programmatically

## Learn More

- [CARTO CLI Documentation](https://docs.carto.com/carto-user-manual/carto-cli)
- [CARTO Platform Documentation](https://docs.carto.com/)
- [CARTO CLI on npm](https://www.npmjs.com/package/@carto/carto-cli)

## Contributing

To update or improve these skills, submit a pull request with your changes. Ensure that:

- Documentation is clear and accurate
- Examples are tested and working
- Markdown formatting is consistent

# Floci MCP Server

Model Context Protocol (MCP) server written in Python to interact with Floci.io (local AWS emulator and Sidecar) and its Infrastructure Applications Marketplace.

This MCP server enables AI agents (like Claude Desktop or Cursor) to directly interface with Floci via natural language. By connecting through the MCP protocol, your AI can:
- **Audit AWS state:** Query and inspect resources across local AWS services directly.
- **Provision infrastructure:** Deploy and manage Marketplace apps (e.g., PostgreSQL, Redis, MinIO) locally using Docker Compose recipes.
- **Run local diagnostics:** Perform tasks like data seeding, network topology mapping, or test execution to speed up development workflows.
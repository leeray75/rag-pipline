# Model Context Protocol (MCP) Documentation - v1

This directory contains comprehensive, RAG-optimized documentation for the Model Context Protocol (MCP), focused on the Python SDK (v1.27.0).

## Overview

MCP is a protocol for connecting LLMs with external data sources and tools. This documentation covers:

- **Transport mechanisms** (stdio, Streamable HTTP)
- **Server building** with FastMCP
- **Client implementation** patterns
- **Protocol features** and capabilities
- **Testing strategies**

## Document Structure

### Getting Started

| Document | Description | When to Read |
|----------|-------------|--------------|
| [`MCP-PYTHON-SDK-OVERVIEW.md`](MCP-PYTHON-SDK-OVERVIEW.md) | Quick start and architecture overview | First read for beginners |
| [`MCP-TRANSPORTS-PROTOCOL.md`](MCP-TRANSPORTS-PROTOCOL.md) | Transport layer specifications | Understanding server-client communication |

### Core Documentation

| Document | Description | When to Read |
|----------|-------------|--------------|
| [`MCP-SERVER-BUILDING.md`](MCP-SERVER-BUILDING.md) | Building MCP servers with FastMCP | Implementing server-side functionality |
| [`MCP-CLIENT-IMPLEMENTATION.md`](MCP-CLIENT-IMPLEMENTATION.md) | Writing MCP clients | Building client applications |
| [`MCP-PROTOCOL-FEATURES.md`](MCP-PROTOCOL-FEATURES.md) | Protocol-level features reference | Understanding protocol mechanics |

### Advanced Topics

| Document | Description | When to Read |
|----------|-------------|--------------|
| [`MCP-TESTING.md`](MCP-TESTING.md) | Testing strategies and examples | Validating server/client implementations |

## Quick Start

### For Server Developers

1. Read [`MCP-PYTHON-SDK-OVERVIEW.md`](MCP-PYTHON-SDK-OVERVIEW.md) for architecture
2. Follow [`MCP-SERVER-BUILDING.md`](MCP-SERVER-BUILDING.md) for implementation
3. See [`MCP-TESTING.md`](MCP-TESTING.md) for testing

### For Client Developers

1. Read [`MCP-PYTHON-SDK-OVERVIEW.md`](MCP-PYTHON-SDK-OVERVIEW.md) for architecture
2. Follow [`MCP-CLIENT-IMPLEMENTATION.md`](MCP-CLIENT-IMPLEMENTATION.md) for implementation
3. See [`MCP-TESTING.md`](MCP-TESTING.md) for testing

### For Protocol Understanders

1. Read [`MCP-TRANSPORTS-PROTOCOL.md`](MCP-TRANSPORTS-PROTOCOL.md) for transport basics
2. Follow [`MCP-PROTOCOL-FEATURES.md`](MCP-PROTOCOL-FEATURES.md) for protocol details

## Key Concepts

### The Three MCP Primitives

| Primitive | Control | Use Case |
|-----------|---------|----------|
| **Tools** | Model-controlled | LLM functions (API calls, data updates) |
| **Resources** | Application-controlled | Contextual data (files, API responses) |
| **Prompts** | User-controlled | Interactive templates (slash commands) |

### Transport Options

| Transport | Use Case | Security |
|-----------|----------|----------|
| **stdio** | Local, same-host | Local only |
| **Streamable HTTP** | Network, remote | Use HTTPS |

## API Reference Quick Links

### Server API
- [`FastMCP`](MCP-SERVER-BUILDING.md) - Main server class
- [`@app.tool()`](MCP-SERVER-BUILDING.md) - Tool decorator
- [`@app.resource()`](MCP-SERVER-BUILDING.md) - Resource decorator
- [`@app.prompt()`](MCP-SERVER-BUILDING.md) - Prompt decorator

### Client API
- [`ClientSession`](MCP-CLIENT-IMPLEMENTATION.md) - Main client class
- [`call_tool()`](MCP-CLIENT-IMPLEMENTATION.md) - Tool invocation
- [`read_resource()`](MCP-CLIENT-IMPLEMENTATION.md) - Resource access
- [`list_prompts()`](MCP-CLIENT-IMPLEMENTATION.md) - Prompt listing

## Installation

```bash
# Using pip
pip install mcp

# Using uv
uv add mcp
```

## Testing

```bash
# Install test dependencies
pip install inline-snapshot pytest

# Run tests
pytest
```

## Protocol Version

- **SDK Version**: 1.27.0
- **Protocol Version**: 2025-11-25 (latest)
- **JSON Schema**: 2020-12

## Related Resources

- [Official MCP Spec](https://modelcontextprotocol.io/specification/)
- [Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk)

## Contributing

This documentation is auto-generated from the official MCP documentation. For corrections or enhancements, please refer to the upstream resources.

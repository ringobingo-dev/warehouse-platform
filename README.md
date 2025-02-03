# Warehouse Platform

A comprehensive warehouse management platform built with a microservices architecture.

## Project Structure

```
warehouse-platform/
├── services/               # Microservices
│   ├── auth-service/       # Authentication service
│   ├── inventory-service/  # Inventory management
│   └── order-service/      # Order management
├── infrastructure/         # Infrastructure as Code
├── shared/                # Shared libraries and utilities
└── docs/                  # Platform documentation
```

## Services

- **Auth Service**: Handles authentication and authorization
- **Inventory Service**: Manages warehouse inventory
- **Order Service**: Processes and manages orders

## Getting Started

1. Clone the repository with submodules:
   ```bash
   git clone --recursive https://github.com/ringobingo-dev/warehouse-platform.git
   ```

2. Follow setup instructions in each service's README

## Development

- Each service is maintained in its own repository
- Use feature branches for development
- Submit PRs for code review
- CI/CD pipelines handle testing and deployment

## Documentation

Detailed documentation is available in the /docs directory

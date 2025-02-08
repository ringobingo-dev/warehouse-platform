# Changelog

All notable changes to the Warehouse Platform will be documented in this file.

## [0.1.0] - 2024-02-04

### Added
- Initial repository structure setup
- Created main warehouse-platform repository
- Created sub-repositories:
  - warehouse-auth-service
  - warehouse-infrastructure
  - warehouse-shared
  - warehouse-docs

### Changed
- Migrated existing auth service code from warehouse_v1 to warehouse-auth-service
- Organized repository with standard structure:
  - services/
  - infrastructure/
  - shared/
  - docs/

### Fixed
- Removed misplaced requirements.txt from main repository
- Properly initialized git submodules
- Established correct project hierarchy

### Technical Details
- Repository Structure:
  ```
  warehouse-platform/
  ├── .github/                # GitHub workflows
  ├── services/               # Microservices
  │   └── auth-service/       # Authentication service (submodule)
  ├── infrastructure/         # IaC (submodule)
  ├── shared/                 # Shared libraries (submodule)
  ├── docs/                   # Documentation (submodule)
  ├── CHANGELOG.md            # This file
  └── README.md               # Main documentation
  ```

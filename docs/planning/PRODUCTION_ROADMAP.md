# Attack-a-Crack CRM: Path to Production Roadmap

**Version 1.2 | Status: Finalized**

This document outlines the finalized, multi-phase plan to take the Attack-a-Crack CRM from its current alpha state to a stable, secure, and scalable production-ready application. It includes foundational hardening, infrastructure setup, quality engineering, and ongoing development principles.

## Phase 1: Foundational Hardening (Priority: CRITICAL)

This phase addresses all prerequisites for a safe production deployment. All items in this phase are blockers for launch.

### 1.1. Implement User Authentication & Authorization

- **System**: Build an invite-only, email/password-based authentication system using Flask-Login.
- **User Model**: Enhance the User model to include password_hash and a role attribute.
- **Roles**: Create two initial roles: admin and marketer, with the system designed for future expansion.
- **Invite Flow**:
  - An admin can invite new users via email from a dedicated settings page.
  - Invited users receive a secure, one-time link to an account creation page where they set their password.
- **Security**:
  - Enforce password complexity rules on account creation.
  - Protect all application routes (excluding webhooks and login pages) with @login_required.
  - Automatic session timeouts are out of scope for this phase.

### 1.2. Codebase Consolidation & Refinement

- **Obsolete Code Removal**: Perform a dependency analysis and safely delete all identified obsolete files, including services/webhook_sync_service.py, sms_sender.py, and redundant "simple" test files.
- **Test Suite Consolidation**: Merge duplicative test files to create a single, comprehensive test module for each corresponding application module.
- **Secrets Management**: Remove client_secret.json and openphone.key from the repository and its history. Ensure all secrets are managed exclusively through environment variables.
- **Standardize Logging**: Refactor all print() statements used for application logging to use the structured logger defined in logging_config.py.
- **Refine Configuration**: Refactor config.py to use a class-based structure (e.g., DevelopmentConfig, ProductionConfig) to cleanly separate settings for different environments.

### 1.3. UI & Functionality Audit

- **Audit**: Conduct a full audit of the user interface to identify all non-functional UI elements (buttons, links).
- **Remediation**: Disable or remove all "dangling" UI elements. Clearly label features intended for future development as "Coming Soon."
- **Navigation Consolidation**: Merge the Data Imports and System Settings views into a single, intuitive settings area.
- **Documentation**: Create a "UI Polish" backlog to track all identified gaps for future sprints.

### 1.4. Documentation & Utility Script Consolidation

- **Documentation Cleanup**: Consolidate the multiple docs/WEBHOOK_*.md files into a single, definitive WEBHOOK_INTEGRATION.md document. Archive outdated planning documents (PRODPLAN.md) after merging any still-relevant information into the primary ROADMAP.md.
- **Utility Script Reorganization**:
  - Rename the /utils directory to /scripts to clarify its purpose for administrative and one-off tasks.
  - Within /scripts, create subdirectories for organization: data_management, dev_tools, and maintenance.
  - Consolidate the various import scripts, making large_scale_import.py the primary tool and archiving older versions.
  - Move the remaining scripts into the appropriate new subdirectories.

## Phase 2: Production Environment & CI/CD

This phase focuses on building a stable and automated infrastructure for deployment and maintenance.

### 2.1. Hosting & Infrastructure

- **Platform**: Deploy the application on the DigitalOcean App Platform.
- **Configuration**: Use a .do/app.yaml specification file to define all services (web, celery worker, celery beat, postgres, redis).
- **Domain & SSL**: Configure the production domain and utilize the platform's automated SSL certificate provisioning.
- **Monitoring & Alerting**: Configure dashboards in DigitalOcean for key metrics (CPU, Memory, DB Connections, Celery Throughput). Set up Sentry for real-time error alerting on critical production failures.

### 2.2. CI/CD Pipeline (GitHub Actions)

- **Continuous Integration (on push to main)**:
  - Run linter (flake8) and security scanner (bandit).
  - Execute the full pytest suite, including database migration tests.
  - On success, build a versioned Docker image and push it to the DigitalOcean Container Registry.
- **Continuous Deployment (on manual trigger)**:
  - Create a separate, manually-triggered GitHub Action workflow.
  - This workflow will deploy the latest stable image from the registry to the DigitalOcean App Platform.
- **Environments**: The defined workflow will use two environments: local development and production. A staging environment is out of scope.

## Phase 3: Quality & Scalability Engineering

This phase ensures the application is reliable under load and that the data remains clean as the system scales.

### 3.1. Quality Assurance & Testing

- **Priority 1 (End-to-End Campaign Testing)**: Develop comprehensive integration tests for both list-based and filter-based SMS campaign workflows.
- **Priority 2 (Webhook Integrity Testing)**: Build a dedicated test harness for the OpenPhoneWebhookService to simulate and verify every supported webhook event type.
- **Bug Response Policy**:
  - Critical Bugs (impacting SMS campaigns or data integrity): Immediate rollback to the previous stable version.
  - Non-Critical Bugs (minor UI/functional issues): Log and prioritize in the backlog.

### 3.2. Database & Performance

- **Data Integrity**:
  - Enforce UNIQUE constraints on Contact.phone and Contact.email.
  - Implement a "merge-on-match" strategy for all data imports to enrich existing contacts.
  - Develop a conflict resolution queue to flag imports with conflicting data for manual admin review.
- **Performance Optimization**:
  - Implement server-side pagination on all primary list views (Contacts, Properties, etc.), defaulting to 100 records per page.
  - Conduct a full query audit and apply eager loading (joinedload) to prevent N+1 performance issues.
- **Schema Future-Proofing**:
  - Add lead_source (String) and customer_since (Date) to the Contact model.
  - Add property_type (String) to the Property model.

## Phase 4: Ongoing Engineering & Quality Standards

This phase defines the operational principles that will guide all future development to ensure long-term quality and maintainability.

- **Test-Driven Development Policy**: All new features, bug fixes, and refactors must be accompanied by a comprehensive suite of unit and integration tests that validate both the feature's internal logic and its interactions with other system components. Pull requests will not be merged without passing all checks in the CI pipeline.

- **Database Migration Testing**: The CI pipeline will include a dedicated step to test the database migration process, ensuring that schema changes can be applied to a production-like database without data loss or errors.

- **UI/UX Consistency Policy**: A simple, one-page Style Guide will be created and maintained. All new UI components must adhere to this guide to ensure a consistent and professional user experience.

- **Continuous Backlog Refinement**: The "UI Polish" backlog created in Phase 1 will be actively maintained. A portion of each development cycle will be allocated to addressing items from this backlog, ensuring continuous improvement of the user experience.
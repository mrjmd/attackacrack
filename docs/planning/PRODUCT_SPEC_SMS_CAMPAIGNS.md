# Product Specification: OpenPhone Integration & SMS Campaigns v1.0

**Status:** Final Draft  
**Date:** August 21, 2025  
**Author:** Product Manager

## 1. Executive Summary & Immediate Priorities

### 1.1. Overview

This document details the multi-phase product and engineering plan to build a sophisticated, reliable, and intelligent SMS campaign feature on top of our OpenPhone integration. The ultimate goal is to create a powerful, automated outreach engine that serves as a core pillar of our platform's value proposition.

### 1.2. Context & Driving Need

Following a recent, large-scale code refactoring, our existing OpenPhone webhook integration, which is critical for real-time data synchronization, was broken. This event highlights the need to not only restore this functionality but to build a robust, testable, and monitored foundation for all future OpenPhone-related features. The features detailed in this specification are predicated on first achieving this rock-solid data sync reliability.

### 1.3. Immediate MVP Priorities

Our development will be focused on a single, primary goal for the MVP: **Launch a reliable, stateful, "trickle" SMS campaign engine**. This breaks down into three core priorities:

1. **Fix & Harden Data Sync:** Restore and thoroughly test all webhook handlers. Implement a health check and reconciliation script to guarantee data integrity.

2. **Build the Core Campaign Engine:** Create the backend logic for scheduled, throttled sending of personalized SMS messages.

3. **Enable Audience Creation:** Implement a streamlined CSV import process with mandatory phone number validation to build campaign lists.

## 2. Phase 1 (MVP): The Foundation for Automated Outreach

This phase is focused on building the core, reliable components needed to run our first automated campaigns.

### 2.1. Data Sync & Reliability (The Foundation)

#### 2.1.1. Webhooks

**Goal:** Achieve 100% reliability for all incoming OpenPhone events, with robust monitoring.

**User Story:** As the system, I want to process every event from OpenPhone in real-time so that our application data is always up-to-date and I can trigger automated workflows.

**Functional Requirements:**

- **Restore Functionality:** All existing webhook handlers must be fixed, refactored for the new architecture, and have comprehensive test coverage.

- **Complete Event Coverage:** Build and test handlers for all critical event types:
  - `message.received`: Must robustly handle media attachments (images, etc.) and store them reliably. This is a business-critical data source.
  - `call.completed`: Log the call, its duration, and link to the recording.
  - `call.missed`: Create a distinct "missed call" activity log entry.
  - `call.recording.ready`: Update the call activity with the recording URL.
  - `call.transcript.ready`: Store the full call transcript.
  - `call.summary.ready`: Store any AI-generated call summaries.

- **Local Development Proxy:** Implement a secure endpoint on the production server that can proxy webhook events to a whitelisted IP address. This provides a stable endpoint for local development without relying on third-party tunneling services.

- **Health Check Service:**
  - A Celery task will run hourly.
  - It will use two dedicated internal OpenPhone numbers to send a test message to itself.
  - It will then verify that the `message.received` webhook for this test message was successfully processed by our application within a 2-minute window.
  - **Alerting:** If the health check fails, an automated email alert will be sent to a designated address.

#### 2.1.2. Reconciliation Script

**Goal:** Create a reliable daily script to guarantee no data is ever missed due to webhook downtime or other transient failures.

**User Story:** As the system, I want to daily compare my data with OpenPhone's data and pull in anything I'm missing, so that I can guarantee 100% data integrity over time.

**Functional Requirements:**

- **Execution:** The script will be a Celery task scheduled to run once every 24 hours.

- **Source of Truth:** For the MVP, OpenPhone is the canonical source of truth. The script will only add missing data to our system; it will not modify existing data.

- **Logic:**
  - The script will query the OpenPhone API for all conversations and activities that have occurred since the last successful run.
  - It will use unique identifiers (conversationId, messageId, callId) to check for the existence of these records in our database.
  - Any records that do not exist locally will be created. This idempotent logic prevents the creation of duplicates.

### 2.2. Audience Creation (Contact Lists)

#### 2.2.1. CSV Importer

**Goal:** Provide a simple, reliable way to create a static contact list from a CSV file.

**User Story:** As a user, I want to upload a CSV of contacts and have it intelligently create a new contact list, so I can easily define my campaign audience.

**Functional Requirements:**

- **Code Refactoring:** The existing CSV import logic will be audited and refactored to simplify its structure, improve error handling, and align with the service/repository pattern.

- **Column Mapping:** The importer will use smart auto-detection for common headers (e.g., first_name, phone, email).

- **Duplicate Handling:** If an imported row contains a phone number that already exists in the main contact database, the system will not create a new contact. It will add the existing contact to the new CampaignList and log this action in the import summary.

#### 2.2.2. Phone Number Validation

**Goal:** Ensure we only attempt to send messages to valid, mobile phone numbers to protect our deliverability and comply with carrier standards.

**User Story:** As a user, when I upload a list, I want the system to automatically verify the phone numbers so that my campaign's failure rate is minimized and my sending reputation is protected.

**Functional Requirements:**

- **Integration:** We will integrate with a low-cost validation service, NumVerify, via their API.

- **Mandatory Workflow:** This will be a mandatory, non-skippable step in the CSV import process.

- **Process:**
  - After a CSV is parsed, the system will show a preview (e.g., "Found 2,500 contacts").
  - A background job will be triggered to validate each phone number in the file.
  - The final CampaignList will only be created with contacts that return a `valid: true` and `line_type: mobile` status from the API.
  - A summary of the validation results (e.g., "2,350 valid mobile numbers found, 150 invalid or landline numbers skipped") will be displayed.

### 2.3. Campaign Engine & UI

#### 2.3.1. Campaign Creation User Interface

**Goal:** Provide a simple, intuitive, single-page interface for creating and configuring campaigns.

**User Story:** As a user, I want to set up a new campaign, including the message, audience, and schedule, from a single screen, so that the process is fast and efficient.

**UI Design:**

- The "New Campaign" page will be a single, well-structured form, not a multi-step wizard.

- **Section 1: Setup:**
  - Campaign Name text input.
  - Message A text area with personalization token buttons (`{{first_name}}`, etc.).
  - A live preview of the rendered message.

- **Section 2: Audience:**
  - A dropdown to select an existing Contact List.
  - A button to "Create New List," which opens the CSV import flow in a modal or new tab.

- **Section 3: Scheduling & Rules:**
  - Checkboxes for days of the week (Mon, Tue, Wed, Thu, Fri).
  - A time input for the daily send time.
  - A number input for the Messages per run threshold.
  - A clear, read-only display of the mandatory rule: "Contacts with any previous communication will be skipped and added to a review list."

- **Section 4: Actions:**
  - "Save as Draft" button.
  - "Activate Campaign" button, which shows a final confirmation summary before starting.

#### 2.3.2. Scheduling & Sending Logic

**Goal:** Build a robust, stateful "trickle" campaign engine.

**Functional Requirements:**

- **State Management:** Campaigns will have statuses: `Draft`, `Active`, `Paused`, `Completed`.

- **Scheduler:** A Celery Beat schedule will trigger a master task every minute. This task will check for any Active campaigns whose scheduled send time has arrived.

- **Throttled Sending:** For each due campaign, a task will be dispatched to send messages to the next N contacts in its list, where N is the campaign's threshold.

- **Stateful Tracking:** The system must maintain a persistent pointer (e.g., the index or ID of the last contact messaged) for each campaign to ensure it never re-sends to the same contact or skips anyone.

- **Pausing/Resuming:** Pausing a campaign sets its status to `Paused`. The scheduler will ignore it. When resumed, the campaign's status becomes `Active`, and it will pick up exactly where it left off at its next scheduled send time. No contacts will be skipped.

#### 2.3.3. A/B Testing (MVP)

**Goal:** Enable basic message variant testing without the complexity of an analytics backend.

**User Story:** As a user, I want to test two different messages in a single campaign so I can manually see which one gets better responses.

**Functional Requirements:**

- The UI will include an "Add Message B" button.
- If Message B is present, the campaign will send Message A to the first 50% of the contact list and Message B to the second 50%.
- There will be no in-app analytics or automatic winner-picking in the MVP.

## 3. Phase 2: Intelligence & Scale

- **AI-Assisted Follow-ups:** Implement the "human-in-the-loop" workflow using the Gemini API to generate contextual follow-up messages for previously contacted leads, placing them in an approval queue.

- **Advanced Audience Tools:**
  - Build the visual CSV mapping interface for importing complex datasets.
  - Build the "Duplicate Resolution" UI for manual contact merging.
  - Integrate a dedicated DNC (Do Not Call) scrubbing service.

- **Advanced Campaigns:**
  - Build an analytics dashboard to track reply rates and other key metrics for campaigns and A/B tests.
  - Implement logic to automatically pause a losing A/B test variant and continue sending the winner.

## 4. Future Roadmap

- **Full AI Automation:** Introduce a "fully automated" mode for AI-generated follow-ups.
- **Dynamic Contact Lists:** Build a query engine to create lists based on contact properties and activities (e.g., "all contacts who haven't replied in 30 days").
- **Reverse Sync:** Build the functionality to push updates (e.g., new contacts, notes) from our system back to OpenPhone.
- **Multi-Developer Tooling:** Migrate the local development webhook solution to a service like smee.io.

## 5. Critical Considerations & Blind Spots

This section outlines crucial non-functional requirements and risks that must be considered throughout development.

### 5.1. SMS Compliance (TCPA & CTIA)

**Risk:** Non-compliance can lead to significant fines and carrier blacklisting. This is a business-critical risk.

**MVP Requirements:**

- **Consent:** Our application logic must be built around the principle of "express written consent." For the MVP, this consent is assumed to be handled outside our system (e.g., during lead capture), but the UI should include disclaimers.

- **Identification:** Every campaign message sent must clearly identify our business as the sender.

- **Opt-Out:** We must handle STOP replies. The webhook handler for incoming messages must be programmed to recognize the "STOP" keyword. When received, the corresponding contact must be flagged as "Opted-Out" and automatically excluded from all future campaigns. We must also send one final confirmation message (e.g., "You have been unsubscribed...").

### 5.2. Deliverability & Rate Limits

- **OpenPhone API:** Their documentation states a rate limit of 10 requests per second.

- **Mitigation:** Our "trickle" campaign architecture is inherently designed to respect this. By sending messages in small, scheduled batches rather than all at once, we will naturally stay well below this limit. The reconciliation script must also be built with appropriate delays to avoid bursting the API.

---

## Implementation Priority Order

Based on the critical path analysis, the implementation should follow this sequence:

### Week 1: Foundation
1. Fix and test all webhook handlers
2. Implement webhook health check service
3. Build reconciliation script

### Week 2: Data Pipeline
1. Refactor CSV import logic
2. Integrate NumVerify phone validation
3. Test end-to-end contact import flow

### Week 3: Campaign Core
1. Build campaign data model and state machine
2. Implement Celery Beat scheduler
3. Create throttled sending logic

### Week 4: UI & Launch
1. Build campaign creation UI
2. Implement A/B testing logic
3. Add opt-out handling
4. Final testing and deployment

---

*Document Version: 1.0*  
*Last Updated: August 21, 2025*
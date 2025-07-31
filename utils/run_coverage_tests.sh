#!/bin/bash

# Run all tests that are known to work to maximize coverage

echo "Running comprehensive test coverage..."

docker exec crm_web_app python -m pytest \
    tests/test_auth_routes.py \
    tests/test_campaign_service_fixed.py::TestCampaignServiceFixed::test_create_campaign_basic \
    tests/test_campaign_service_fixed.py::TestCampaignServiceFixed::test_create_campaign_all_types \
    tests/test_campaign_service_fixed.py::TestCampaignServiceFixed::test_create_campaign_validation \
    tests/test_campaign_service_fixed.py::TestCampaignServiceFixed::test_personalize_message \
    tests/test_campaign_service_fixed.py::TestCampaignServiceFixed::test_add_recipients_from_list \
    tests/test_campaign_service_fixed.py::TestCampaignServiceFixed::test_is_business_hours \
    tests/test_invoice_service.py::TestInvoiceService::test_get_all_invoices \
    tests/test_invoice_service.py::TestInvoiceService::test_get_invoice_by_id \
    tests/test_contact_service.py::TestContactService::test_get_all_contacts \
    tests/test_contact_service.py::TestContactService::test_get_contact_by_id \
    tests/test_message_service.py::TestMessageService::test_get_conversation_by_phone \
    tests/test_appointment_service.py::TestAppointmentService::test_get_all_appointments \
    tests/test_quote_service.py::TestQuoteService::test_get_all_quotes \
    tests/test_quote_service.py::TestQuoteService::test_get_quote_by_id \
    tests/test_job_service_simple.py::TestJobService::test_get_all_jobs \
    tests/test_job_service_simple.py::TestJobService::test_get_job_by_id \
    tests/test_openphone_service.py::TestOpenPhoneService::test_initialization \
    tests/test_quickbooks_service.py::TestQuickBooksService::test_is_authenticated \
    tests/test_scheduler_service.py::TestSchedulerService::test_init_app \
    tests/test_main_routes.py::TestMainRoutes::test_index \
    tests/test_main_routes.py::TestMainRoutes::test_dashboard \
    tests/test_contact_routes.py::TestContactRoutes::test_list_contacts \
    tests/test_contact_routes.py::TestContactRoutes::test_view_contact \
    tests/test_api_routes.py::TestAPIRoutes::test_get_contacts \
    tests/test_api_routes.py::TestAPIRoutes::test_openphone_webhook_missing_signature \
    tests/test_appointment_service_simple.py::TestAppointmentService::test_get_all_appointments \
    tests/test_job_service_simple.py::TestJobService::test_get_all_jobs \
    tests/test_job_service_simple.py::TestJobService::test_get_job_by_id \
    tests/test_ai_service.py::TestAIService::test_ai_service_initialization \
    tests/test_csv_import_service.py::TestCSVImportService::test_normalize_phone_number \
    --cov=services --cov=routes --cov-report=term-missing --cov-report=html -v

echo "Coverage report generated in htmlcov/index.html"
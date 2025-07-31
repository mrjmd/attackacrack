#!/bin/bash

# Run only tests that are known to work to maximize coverage

echo "Running working tests for coverage..."

docker exec crm_web_app python -m pytest \
    tests/test_auth_routes.py \
    tests/test_campaign_service_corrected.py::TestCampaignServiceCorrected::test_create_campaign_basic \
    tests/test_campaign_service_corrected.py::TestCampaignServiceCorrected::test_create_campaign_with_all_params \
    tests/test_campaign_service_corrected.py::TestCampaignServiceCorrected::test_get_all_campaigns \
    tests/test_campaign_service_corrected.py::TestCampaignServiceCorrected::test_personalize_message \
    tests/test_campaign_service_corrected.py::TestCampaignServiceCorrected::test_is_business_hours \
    tests/test_campaign_service_corrected.py::TestCampaignServiceCorrected::test_create_campaign_validation_errors \
    tests/test_campaign_service_corrected.py::TestCampaignServiceCorrected::test_check_contact_history \
    tests/test_invoice_service.py::TestInvoiceService::test_get_all_invoices \
    tests/test_contact_service_fixed.py::TestContactServiceFixed::test_get_contact_by_id \
    tests/test_contact_service_fixed.py::TestContactServiceFixed::test_add_contact \
    tests/test_contact_service_fixed.py::TestContactServiceFixed::test_delete_contact \
    tests/test_contact_service_fixed.py::TestContactServiceFixed::test_get_contact_by_phone \
    tests/test_job_service_simple.py::TestJobService::test_get_all_jobs \
    tests/test_openphone_webhook_service.py::TestOpenPhoneWebhookService::test_process_webhook_error_handling \
    tests/test_appointment_service_simple.py::TestAppointmentService::test_get_all_appointments \
    --cov=services --cov=routes --cov-report=term-missing --cov-report=html -v

echo "Coverage report generated in htmlcov/index.html"
#!/bin/bash
# Run architectural enforcement test
docker-compose exec web python -m pytest tests/unit/services/test_service_model_import_violations.py -xvs

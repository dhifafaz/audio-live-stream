"""
Unit tests for FastAPI endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, Mock
from datetime import datetime
import pytz

from source.services.api import app


class TestAPIEndpoints:
    """Test suite for API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "Case Similarity Processing API"
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Case Similarity Processing API"
        assert "endpoints" in data
    
    @patch('source.services.api.processor')
    def test_process_case_success(self, mock_processor, client, sample_input_data_model):
        """Test successful case processing."""
        # Mock processor response
        mock_processor.process_data = AsyncMock(return_value=(
            {
                "id_case": "BOM-TSL-202510-01-ABCD",
                "id": "test-data-id",
                "case_name": "Test Case"
            },
            2  # similar_cases_count
        ))
        
        response = client.post("/process-case", json=sample_input_data_model)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["case_id"] == "BOM-TSL-202510-01-ABCD"
        assert data["similar_cases_count"] == 2
    
    @patch('source.services.api.processor')
    def test_process_case_invalid_data(self, mock_processor, client):
        """Test case processing with invalid data."""
        invalid_data = {
            "score_threshold": 0.85,
            "data": {
                # Missing required fields
                "input": "test"
            }
        }
        
        response = client.post("/process-case", json=invalid_data)
        
        assert response.status_code == 422  # Validation error
    
    @patch('source.services.api.processor')
    def test_process_case_async(self, mock_processor, client, sample_input_data_model):
        """Test asynchronous case processing."""
        response = client.post("/process-case-async", json=sample_input_data_model)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "task_id" in data
    
    @patch('source.services.api.processor')
    def test_find_similar_cases(self, mock_processor, client):
        """Test finding similar cases."""
        # Mock processor response
        mock_processor._create_qdrant_filter = Mock()
        mock_processor._find_similar_data = AsyncMock(return_value=[
            {
                "similarity_score": 0.95,
                "payload": {"id_case": "BOM-TSL-202510-01-ABCD"},
                "metadata": {}
            }
        ])
        
        response = client.get(
            "/find-similar",
            params={
                "text": "test query",
                "coordinate_lat": -6.2680494,
                "coordinate_lon": 106.68715,
                "score_threshold": 0.8,
                "limit": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["similarity_score"] == 0.95
    
    @patch('source.services.api.processor')
    def test_get_latest_report(self, mock_processor, client):
        """Test getting latest report."""
        # Mock processor response
        mock_processor.get_reports_by_case_id = AsyncMock(return_value=[
            {
                "id": "report-1",
                "id_case": "BOM-TSL-202510-01-ABCD",
                "input": "Test report",
                "created_at": "2025-10-20 10:30:00 +0700",
                "timestamp": 1729400000
            }
        ])
        
        request_data = {
            "case_id": "BOM-TSL-202510-01-ABCD",
            "start_time": "2025-10-01 00:00:00 +0700",
            "end_time": "2025-10-31 23:59:59 +0700",
            "limit": 10
        }
        
        response = client.post("/report/latest", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == "BOM-TSL-202510-01-ABCD"
        assert data["reports_found"] == 1
        assert data["latest_report"]["id"] == "report-1"
    
    @patch('source.services.api.processor')
    def test_get_latest_report_not_found(self, mock_processor, client):
        """Test getting latest report when no reports exist."""
        # Mock no reports found
        mock_processor.get_reports_by_case_id = AsyncMock(return_value=[])
        
        request_data = {
            "case_id": "NONEXISTENT",
            "limit": 10
        }
        
        response = client.post("/report/latest", json=request_data)
        
        assert response.status_code == 404

"""
Unit tests for Pydantic models.
"""
import pytest
from pydantic import ValidationError
from datetime import datetime

from source.models.api_models import (
    CoordinateModel,
    LocationDetailsModel,
    CaseDataModel,
    InputDataModel,
    ProcessingResponseModel,
    ProcessingStatusEnum,
    ReportModel,
    GetLatestReportRequest,
    LatestReportResponse
)


class TestCoordinateModel:
    """Test suite for CoordinateModel."""
    
    def test_coordinate_with_lon(self):
        """Test coordinate creation with lon field."""
        coord = CoordinateModel(lat=-6.2680494, lon=106.68715)
        assert coord.lat == -6.2680494
        assert coord.lon == 106.68715
    
    def test_coordinate_with_long(self):
        """Test coordinate creation with long field (should map to lon)."""
        coord = CoordinateModel(lat=-6.2680494, long=106.68715)
        assert coord.lat == -6.2680494
        assert coord.lon == 106.68715
    
    def test_coordinate_optional_fields(self):
        """Test coordinate with optional fields."""
        coord = CoordinateModel()
        assert coord.lat is None
        assert coord.lon is None


class TestCaseDataModel:
    """Test suite for CaseDataModel."""
    
    def test_valid_case_data(self, sample_location_details):
        """Test valid case data creation."""
        case_data = CaseDataModel(
            input="Test input",
            created_at="2025-10-20 10:30:00 +0700",
            location_details=sample_location_details
        )
        
        assert case_data.input == "Test input"
        assert case_data.created_at == "2025-10-20 10:30:00 +0700"
    
    def test_invalid_created_at_format(self, sample_location_details):
        """Test case data with invalid created_at format."""
        with pytest.raises(ValidationError):
            CaseDataModel(
                input="Test input",
                created_at="2025-10-20",  # Invalid format
                location_details=sample_location_details
            )
    
    def test_optional_fields(self, sample_location_details):
        """Test case data with optional fields."""
        case_data = CaseDataModel(
            input="Test input",
            created_at="2025-10-20 10:30:00 +0700",
            location_details=sample_location_details,
            sketch="https://example.com/sketch.png",
            images=[{"url": "https://example.com/image.jpg"}],
            audios=[],
            videos=[],
            files=[],
            first_name="John",
            username="johndoe"
        )
        
        assert case_data.sketch == "https://example.com/sketch.png"
        assert len(case_data.images) == 1
        assert case_data.first_name == "John"


class TestInputDataModel:
    """Test suite for InputDataModel."""
    
    def test_valid_input_data(self, sample_case_data):
        """Test valid input data creation."""
        input_data = InputDataModel(
            score_threshold=0.85,
            limit=5,
            radius_coordinate=300.0,
            report_type="BOM",
            data=sample_case_data
        )
        
        assert input_data.score_threshold == 0.85
        assert input_data.limit == 5
        assert input_data.radius_coordinate == 300.0
        assert input_data.report_type == "BOM"
    
    def test_default_values(self, sample_case_data):
        """Test default values for optional fields."""
        input_data = InputDataModel(data=sample_case_data)
        
        assert input_data.score_threshold == 0.85
        assert input_data.limit == 5
        assert input_data.radius_coordinate == 300.0
        assert input_data.report_type == "BOM"


class TestProcessingResponseModel:
    """Test suite for ProcessingResponseModel."""
    
    def test_success_response(self):
        """Test successful processing response."""
        response = ProcessingResponseModel(
            status=ProcessingStatusEnum.SUCCESS,
            message="Case processed successfully",
            case_id="BOM-TSL-202510-01-ABCD",
            data_id="test-data-id",
            similar_cases_count=3,
            is_new_case=False,
            processing_time=1.234
        )
        
        assert response.status == ProcessingStatusEnum.SUCCESS
        assert response.case_id == "BOM-TSL-202510-01-ABCD"
        assert response.similar_cases_count == 3
        assert response.is_new_case is False
    
    def test_error_response(self):
        """Test error processing response."""
        response = ProcessingResponseModel(
            status=ProcessingStatusEnum.ERROR,
            message="Processing failed",
            is_new_case=False
        )
        
        assert response.status == ProcessingStatusEnum.ERROR
        assert response.message == "Processing failed"


class TestReportModel:
    """Test suite for ReportModel."""
    
    def test_valid_report(self):
        """Test valid report creation."""
        report = ReportModel(
            id="report-123",
            case_id="BOM-TSL-202510-01-ABCD",
            report_text="Test report content",
            created_at="2025-10-20 10:30:00 +0700"
        )
        
        assert report.id == "report-123"
        assert report.case_id == "BOM-TSL-202510-01-ABCD"
        assert report.report_text == "Test report content"


class TestGetLatestReportRequest:
    """Test suite for GetLatestReportRequest."""
    
    def test_valid_request(self):
        """Test valid report request."""
        request = GetLatestReportRequest(
            case_id="BOM-TSL-202510-01-ABCD",
            start_time="2025-10-01 00:00:00 +0700",
            end_time="2025-10-31 23:59:59 +0700",
            limit=10
        )
        
        assert request.case_id == "BOM-TSL-202510-01-ABCD"
        assert request.limit == 10
    
    def test_default_limit(self):
        """Test default limit value."""
        request = GetLatestReportRequest(case_id="BOM-TSL-202510-01-ABCD")
        assert request.limit == 10


class TestLatestReportResponse:
    """Test suite for LatestReportResponse."""
    
    def test_valid_response(self):
        """Test valid latest report response."""
        report = ReportModel(
            id="report-123",
            case_id="BOM-TSL-202510-01-ABCD",
            report_text="Test report",
            created_at="2025-10-20 10:30:00 +0700"
        )
        
        response = LatestReportResponse(
            case_id="BOM-TSL-202510-01-ABCD",
            reports_found=5,
            latest_report=report
        )
        
        assert response.status == "success"
        assert response.case_id == "BOM-TSL-202510-01-ABCD"
        assert response.reports_found == 5
        assert response.latest_report.id == "report-123"

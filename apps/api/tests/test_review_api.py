"""Tests for the review API endpoints.

This test file validates the structure of the review API endpoints.
The tests use a mock database dependency to avoid requiring a real database connection.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from src.main import app
from src.database import get_db


def create_finalize_mock(total_docs=0, reviewed=0, rejected=0, job_exists=True):
    """Create a mock database for finalize_review tests.
    
    The finalize_review endpoint calls execute() 4 times:
    1. Job existence check
    2. Total document count
    3. Reviewed document count  
    4. Rejected document count
    """
    mock_db = AsyncMock()
    
    def make_execute_mock(scalar_value=None):
        """Create a mock result for execute with a specific scalar value."""
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=scalar_value)
        mock_result.all = MagicMock(return_value=[])
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        if scalar_value is None and job_exists:
            mock_result.scalar_one_or_none = MagicMock(return_value=MagicMock(id="test-job-id"))
        else:
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
        return mock_result
    
    # Track how many times execute is called
    execute_call_count = 0
    
    async def execute_mock(query):
        nonlocal execute_call_count
        execute_call_count += 1
        
        # Determine what scalar value to return based on call order
        if execute_call_count == 1:
            # Job existence check - returns mock job if job_exists
            return make_execute_mock(None)
        elif execute_call_count == 2:
            # Total document count
            return make_execute_mock(total_docs)
        elif execute_call_count == 3:
            # Reviewed document count
            return make_execute_mock(reviewed)
        elif execute_call_count == 4:
            # Rejected document count
            return make_execute_mock(rejected)
        return make_execute_mock(0)
    
    mock_db.execute = execute_mock
    mock_db.begin = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    
    return mock_db


@pytest.fixture
async def client():
    """Create a test client with mocked database dependency."""
    mock_db = AsyncMock()
    
    def make_execute_mock():
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=0)
        mock_result.all = MagicMock(return_value=[])
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        return mock_result
    
    async def execute_mock(query):
        return make_execute_mock()
    
    mock_db.execute = execute_mock
    mock_db.begin = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    
    def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_review_summary_requires_valid_job(client):
    """Summary endpoint should return 200 with counts for non-existent job."""
    response = await client.get(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000/review/summary"
    )
    # Summary endpoint should return 200 even for non-existent job (with zero counts)
    assert response.status_code == 200
    data = response.json()
    assert "total_documents" in data
    assert "approved" in data
    assert "rejected" in data
    assert "edited" in data
    assert "pending" in data
    assert "all_reviewed" in data


@pytest.mark.asyncio
async def test_finalize_requires_all_reviewed():
    """Finalize should reject if not all documents are reviewed.
    
    This test uses 1 total doc, 0 reviewed (so 0 < 1, triggering 400).
    """
    mock_db = create_finalize_mock(total_docs=1, reviewed=0)
    
    def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/jobs/00000000-0000-0000-0000-000000000000/review/finalize"
        )
        
        # Should return 400 because not all documents are reviewed (0 < 1)
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Not all documents reviewed" in data["detail"]
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_finalize_all_reviewed():
    """Finalize should succeed when all documents are reviewed."""
    # Create a client with all documents reviewed (1 total, 1 reviewed)
    mock_db = create_finalize_mock(total_docs=1, reviewed=1)
    
    def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/jobs/00000000-0000-0000-0000-000000000000/review/finalize"
        )
        
        # Should return 200 when all documents are reviewed
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "finalized"
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_finalize_job_not_found():
    """Finalize should return 404 for non-existent job."""
    # Create a mock that returns None for job existence check
    mock_db = create_finalize_mock(job_exists=False)
    
    def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/jobs/00000000-0000-0000-0000-000000000000/review/finalize"
        )
        
        # Should return 404 because job doesn't exist
        assert response.status_code == 404
    
    # Clean up
    app.dependency_overrides.clear()

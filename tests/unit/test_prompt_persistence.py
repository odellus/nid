"""
Unit tests for prompt template persistence.

These tests verify:
- Direct lookup by template string content
- Creation of new prompts when not found
- ID generation for new prompts
- Retrieval of existing prompts
"""

import pytest
from sqlalchemy.orm import Session as SQLAlchemySession

from nid.agent.db import Prompt


class TestPromptLookup:
    """Test prompt lookup by template content."""
    
    @pytest.mark.asyncio
    async def test_find_prompt_by_template_exact_match(self, db_session):
        """Test that we can find a prompt by exact template match."""
        # Create a test prompt
        template = "You are a test agent. Workspace: {{workspace}}"
        prompt = Prompt(
            id="test-prompt-v1",
            name="Test Prompt",
            template=template,
        )
        db_session.add(prompt)
        db_session.commit()
        
        # Lookup by template
        found = db_session.query(Prompt).filter_by(template=template).first()
        
        assert found is not None
        assert found.id == "test-prompt-v1"
        assert found.template == template
    
    @pytest.mark.asyncio
    async def test_find_prompt_no_match_returns_none(self, db_session):
        """Test that lookup returns None when template doesn't exist."""
        template = "Non-existent template"
        
        found = db_session.query(Prompt).filter_by(template=template).first()
        
        assert found is None
    
    @pytest.mark.asyncio
    async def test_template_must_be_exact_match(self, db_session):
        """Test that template lookup requires exact match."""
        template = "You are a test agent. Workspace: {{workspace}}"
        prompt = Prompt(
            id="test-prompt-v1",
            name="Test Prompt",
            template=template,
        )
        db_session.add(prompt)
        db_session.commit()
        
        # Different whitespace should not match
        different = "You are a test agent. Workspace: {{workspace}} "  # Extra space
        found = db_session.query(Prompt).filter_by(template=different).first()
        
        assert found is None


class TestPromptCreation:
    """Test creation of new prompts."""
    
    @pytest.mark.asyncio
    async def test_create_new_prompt(self, db_session):
        """Test creating a new prompt."""
        template = "New prompt template"
        prompt_id = "new-prompt-v1"
        
        prompt = Prompt(
            id=prompt_id,
            name="New Prompt",
            template=template,
        )
        db_session.add(prompt)
        db_session.commit()
        
        # Verify it was saved
        found = db_session.query(Prompt).filter_by(id=prompt_id).first()
        assert found is not None
        assert found.template == template
    
    @pytest.mark.asyncio
    async def test_create_prompt_with_generated_id(self, db_session):
        """Test creating a prompt with auto-generated ID."""
        import hashlib
        
        template = "Template with generated ID"
        # Simulate ID generation
        prompt_id = f"prompt-{hashlib.sha256(template.encode()).hexdigest()[:12]}"
        
        prompt = Prompt(
            id=prompt_id,
            name="Generated ID Prompt",
            template=template,
        )
        db_session.add(prompt)
        db_session.commit()
        
        # Verify it was saved with generated ID
        found = db_session.query(Prompt).filter_by(template=template).first()
        assert found is not None
        assert found.id == prompt_id
    
    @pytest.mark.asyncio
    async def test_prompt_has_timestamp(self, db_session):
        """Test that prompts get creation timestamps."""
        from datetime import datetime
        
        template = "Timestamped prompt"
        prompt = Prompt(
            id="timestamped-v1",
            name="Timestamped Prompt",
            template=template,
        )
        db_session.add(prompt)
        db_session.commit()
        
        found = db_session.query(Prompt).filter_by(id="timestamped-v1").first()
        assert found.created_at is not None
        assert isinstance(found.created_at, datetime)


class TestPromptLookupOrCreate:
    """Test the lookup-or-create pattern."""
    
    @pytest.mark.asyncio
    async def test_lookup_existing_prompt(self, db_session):
        """Test that existing prompt is returned, not duplicated."""
        template = "Existing template"
        original = Prompt(
            id="original-v1",
            name="Original Prompt",
            template=template,
        )
        db_session.add(original)
        db_session.commit()
        
        # Try to find existing
        found = db_session.query(Prompt).filter_by(template=template).first()
        
        assert found is not None
        assert found.id == "original-v1"
        
        # Should only be one prompt with this template
        count = db_session.query(Prompt).filter_by(template=template).count()
        assert count == 1
    
    @pytest.mark.asyncio
    async def test_create_if_not_found(self, db_session):
        """Test that new prompt is created if not found."""
        template = "Brand new template"
        
        # Check if exists
        found = db_session.query(Prompt).filter_by(template=template).first()
        assert found is None
        
        # Create new
        new_prompt = Prompt(
            id="new-v1",
            name="New Prompt",
            template=template,
        )
        db_session.add(new_prompt)
        db_session.commit()
        
        # Now should find it
        found = db_session.query(Prompt).filter_by(template=template).first()
        assert found is not None
        assert found.id == "new-v1"
    
    @pytest.mark.asyncio
    async def test_same_template_always_same_prompt(self, db_session):
        """Test that the same template always returns the same prompt."""
        template = "Consistent template"
        prompt1 = Prompt(
            id="consistent-v1",
            name="Consistent Prompt",
            template=template,
        )
        db_session.add(prompt1)
        db_session.commit()
        
        # Multiple lookups should all return the same
        found1 = db_session.query(Prompt).filter_by(template=template).first()
        found2 = db_session.query(Prompt).filter_by(template=template).first()
        
        assert found1.id == found2.id == "consistent-v1"


class TestPromptDeletion:
    """Test prompt deletion and constraints."""
    
    @pytest.mark.asyncio
    async def test_can_delete_prompt(self, db_session):
        """Test that prompts can be deleted."""
        template = "Deletable template"
        prompt = Prompt(
            id="deletable-v1",
            name="Deletable Prompt",
            template=template,
        )
        db_session.add(prompt)
        db_session.commit()
        
        # Delete
        db_session.delete(prompt)
        db_session.commit()
        
        # Should not find it
        found = db_session.query(Prompt).filter_by(template=template).first()
        assert found is None

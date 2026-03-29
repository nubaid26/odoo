# backend/tests/test_state_machine.py
"""
Approval state machine tests — verify valid/invalid transitions.
"""

from __future__ import annotations

import pytest

from app.domain.enums import ExpenseStatus, UserRole
from app.domain.states import transition_expense


class TestStateMachine:
    """Test the approval state machine transitions."""

    def test_draft_to_submitted(self):
        """DRAFT → SUBMITTED is valid for employee."""
        new_state = transition_expense(
            from_state=ExpenseStatus.DRAFT,
            to_state=ExpenseStatus.SUBMITTED,
            role=UserRole.EMPLOYEE,
        )
        assert new_state == ExpenseStatus.SUBMITTED

    def test_submitted_to_approved_by_manager(self):
        """SUBMITTED → APPROVED is valid for manager."""
        new_state = transition_expense(
            from_state=ExpenseStatus.SUBMITTED,
            to_state=ExpenseStatus.APPROVED,
            role=UserRole.MANAGER,
        )
        assert new_state == ExpenseStatus.APPROVED

    def test_submitted_to_rejected_by_manager(self):
        """SUBMITTED → REJECTED is valid for manager."""
        new_state = transition_expense(
            from_state=ExpenseStatus.SUBMITTED,
            to_state=ExpenseStatus.REJECTED,
            role=UserRole.MANAGER,
        )
        assert new_state == ExpenseStatus.REJECTED

    def test_submitted_to_approved_by_admin(self):
        """SUBMITTED → APPROVED is valid for admin."""
        new_state = transition_expense(
            from_state=ExpenseStatus.SUBMITTED,
            to_state=ExpenseStatus.APPROVED,
            role=UserRole.ADMIN,
        )
        assert new_state == ExpenseStatus.APPROVED

    def test_employee_cannot_approve(self):
        """Employee should not be able to transition to APPROVED."""
        with pytest.raises(ValueError, match="not permitted"):
            transition_expense(
                from_state=ExpenseStatus.SUBMITTED,
                to_state=ExpenseStatus.APPROVED,
                role=UserRole.EMPLOYEE,
            )

    def test_approved_cannot_go_back(self):
        """APPROVED → SUBMITTED should be blocked."""
        with pytest.raises(ValueError, match="Invalid"):
            transition_expense(
                from_state=ExpenseStatus.APPROVED,
                to_state=ExpenseStatus.SUBMITTED,
                role=UserRole.ADMIN,
            )

    def test_draft_to_flagged(self):
        """DRAFT → FLAGGED is valid (set by system via trust scoring)."""
        new_state = transition_expense(
            from_state=ExpenseStatus.DRAFT,
            to_state=ExpenseStatus.FLAGGED,
            role=UserRole.ADMIN,
        )
        assert new_state == ExpenseStatus.FLAGGED

    def test_rejected_is_terminal(self):
        """REJECTED is a terminal state with no outgoing transitions."""
        with pytest.raises(ValueError, match="Invalid"):
            transition_expense(
                from_state=ExpenseStatus.REJECTED,
                to_state=ExpenseStatus.SUBMITTED,
                role=UserRole.EMPLOYEE,
            )

    def test_flagged_to_submitted_by_admin(self):
        """FLAGGED → SUBMITTED is valid for admin (after review)."""
        new_state = transition_expense(
            from_state=ExpenseStatus.FLAGGED,
            to_state=ExpenseStatus.SUBMITTED,
            role=UserRole.ADMIN,
        )
        assert new_state == ExpenseStatus.SUBMITTED

    def test_flagged_to_rejected_by_admin(self):
        """FLAGGED → REJECTED is valid for admin."""
        new_state = transition_expense(
            from_state=ExpenseStatus.FLAGGED,
            to_state=ExpenseStatus.REJECTED,
            role=UserRole.ADMIN,
        )
        assert new_state == ExpenseStatus.REJECTED

    def test_draft_to_approved_admin_auto(self):
        """DRAFT → APPROVED is valid for admin (auto-approve path)."""
        new_state = transition_expense(
            from_state=ExpenseStatus.DRAFT,
            to_state=ExpenseStatus.APPROVED,
            role=UserRole.ADMIN,
        )
        assert new_state == ExpenseStatus.APPROVED

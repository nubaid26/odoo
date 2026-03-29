# backend/app/domain/states.py
"""
Approval state machine — defines valid transitions and enforces them.
Raises ValueError on any invalid transition attempt.
"""

from __future__ import annotations

from app.domain.enums import ExpenseStatus, ApprovalStatus, UserRole


# Valid expense status transitions: {from_state: {to_state: [allowed_roles]}}
VALID_EXPENSE_TRANSITIONS = {
    ExpenseStatus.DRAFT: {
        ExpenseStatus.SUBMITTED: [UserRole.EMPLOYEE, UserRole.MANAGER, UserRole.ADMIN],
        ExpenseStatus.APPROVED: [UserRole.ADMIN],  # auto-approve path
        ExpenseStatus.FLAGGED: [UserRole.ADMIN],
    },
    ExpenseStatus.SUBMITTED: {
        ExpenseStatus.APPROVED: [UserRole.MANAGER, UserRole.ADMIN],
        ExpenseStatus.REJECTED: [UserRole.MANAGER, UserRole.ADMIN],
        ExpenseStatus.FLAGGED: [UserRole.ADMIN],
    },
    ExpenseStatus.FLAGGED: {
        ExpenseStatus.SUBMITTED: [UserRole.ADMIN],  # admin re-enables after review
        ExpenseStatus.REJECTED: [UserRole.ADMIN],
    },
}

# Valid approval step transitions
VALID_APPROVAL_TRANSITIONS = {
    ApprovalStatus.PENDING: {
        ApprovalStatus.APPROVED: [UserRole.MANAGER, UserRole.ADMIN],
        ApprovalStatus.REJECTED: [UserRole.MANAGER, UserRole.ADMIN],
    },
}


def transition_expense(
    from_state: ExpenseStatus,
    to_state: ExpenseStatus,
    role: UserRole,
) -> ExpenseStatus:
    """
    Validate and execute an expense status transition.

    Args:
        from_state: Current expense status.
        to_state: Desired expense status.
        role: Role of the user attempting the transition.

    Returns:
        The new state if transition is valid.

    Raises:
        ValueError: If the transition is invalid or role not permitted.
    """
    allowed = VALID_EXPENSE_TRANSITIONS.get(from_state, {})
    if to_state not in allowed:
        raise ValueError(
            f"Invalid expense transition: {from_state.value} → {to_state.value}"
        )
    allowed_roles = allowed[to_state]
    if role not in allowed_roles:
        raise ValueError(
            f"Role {role.value} not permitted for transition "
            f"{from_state.value} → {to_state.value}"
        )
    return to_state


def transition_approval(
    from_state: ApprovalStatus,
    to_state: ApprovalStatus,
    role: UserRole,
) -> ApprovalStatus:
    """
    Validate and execute an approval step transition.

    Args:
        from_state: Current approval step status.
        to_state: Desired approval step status.
        role: Role of the user attempting the transition.

    Returns:
        The new state if transition is valid.

    Raises:
        ValueError: If the transition is invalid or role not permitted.
    """
    allowed = VALID_APPROVAL_TRANSITIONS.get(from_state, {})
    if to_state not in allowed:
        raise ValueError(
            f"Invalid approval transition: {from_state.value} → {to_state.value}"
        )
    allowed_roles = allowed[to_state]
    if role not in allowed_roles:
        raise ValueError(
            f"Role {role.value} not permitted for approval transition "
            f"{from_state.value} → {to_state.value}"
        )
    return to_state

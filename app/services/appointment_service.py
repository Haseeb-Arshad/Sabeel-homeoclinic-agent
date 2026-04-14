"""
Appointment orchestration service.
Collects booking requests and stores them as pending for staff confirmation.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.services.db_service import db_service


class AppointmentService:
    """Business logic around appointment requests."""

    @staticmethod
    def _sanitize_phone(phone: str) -> str:
        return re.sub(r"[^+\d]", "", phone)

    def create_pending_request(
        self,
        *,
        name: str,
        phone: str,
        preferred_date: str,
        preferred_time: str,
        reason: str,
        channel: str,
        conversation_id: str = "",
    ) -> dict[str, str]:
        payload = {
            "patient_name": name.strip(),
            "patient_phone": self._sanitize_phone(phone),
            "preferred_date": preferred_date.strip(),
            "preferred_time": preferred_time.strip(),
            "reason": reason.strip() if reason else "Consultation",
            "channel": channel,
            "conversation_id": conversation_id or None,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }

        appointment_id = db_service.create_appointment_request(payload)

        return {
            "appointment_id": appointment_id,
            "status": "pending",
            "message": (
                f"Appointment request created (ID: {appointment_id}). "
                "Our clinic team will confirm your slot shortly via call or WhatsApp."
            ),
        }

    def check_slot_availability(self, preferred_date: str, preferred_time: str) -> dict[str, str]:
        """Simple informational checker; final confirmation is staff-driven."""
        return {
            "status": "pending_confirmation",
            "message": (
                f"Received your preferred time ({preferred_date} at {preferred_time}). "
                "This slot will be verified by clinic staff before final confirmation."
            ),
        }


appointment_service = AppointmentService()

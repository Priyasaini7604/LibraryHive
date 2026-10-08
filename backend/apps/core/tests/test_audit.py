"""Append-only audit trail (LOG-06)."""

import uuid

from django.test import TestCase

from apps.core import audit
from apps.core.context import client_ip_var, request_id_var
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner


class AuditTrailTests(TestCase):
    def test_record_captures_actor_context_and_changes(self):
        owner = make_owner()
        entity = uuid.uuid4()
        rid_token = request_id_var.set("req-1234567890")
        ip_token = client_ip_var.set("203.0.113.9")
        try:
            row = audit.record(
                actor=owner,
                action="plan.update",
                entity_type="plan",
                entity_id=entity,
                changes={"price": ["1200.00", "1400.00"]},
                reason="Seasonal price",
            )
        finally:
            request_id_var.reset(rid_token)
            client_ip_var.reset(ip_token)
        row.refresh_from_db()
        self.assertEqual(row.actor, owner)
        self.assertEqual(row.actor_role, "owner")
        self.assertEqual(row.entity_id, entity)
        self.assertEqual(row.changes, {"price": ["1200.00", "1400.00"]})
        self.assertEqual(row.request_id, "req-1234567890")
        self.assertEqual(row.ip_address, "203.0.113.9")

    def test_system_actor(self):
        row = audit.record(actor=None, action="hold.expired_batch", entity_type="seat", entity_id=uuid.uuid4())
        self.assertEqual(row.actor_role, "system")

    def test_sensitive_fields_are_never_stored(self):
        row = audit.record(
            actor=None,
            action="account.password_reset",
            entity_type="user",
            entity_id=uuid.uuid4(),
            changes={"password": ["a", "b"], "name": ["A", "B"]},
        )
        self.assertEqual(row.changes, {"name": ["A", "B"]})

    def test_rows_cannot_be_updated_or_deleted(self):
        row = audit.record(actor=None, action="x.y", entity_type="seat", entity_id=uuid.uuid4())
        row.reason = "tampered"
        with self.assertRaises(TypeError):
            row.save()
        with self.assertRaises(TypeError):
            row.delete()
        with self.assertRaises(TypeError):
            AuditLog.objects.filter(pk=row.pk).update(reason="tampered")
        with self.assertRaises(TypeError):
            AuditLog.objects.filter(pk=row.pk).delete()
        row.refresh_from_db()
        self.assertEqual(row.reason, "")

    def test_changes_between_reports_only_changed_safe_fields(self):
        diff = audit.changes_between(
            {"name": "Old", "price": 1200, "password": "x", "same": 1},
            {"name": "New", "price": 1400, "password": "y", "same": 1},
        )
        self.assertEqual(diff, {"name": ["Old", "New"], "price": [1200, 1400]})

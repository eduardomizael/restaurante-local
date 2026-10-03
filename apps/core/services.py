from apps.core.models import DomainEvent


def record_event(kind, entity, **details):
    """Append history inside the caller's short write transaction.

    Args:
        kind: Technical event name.
        entity: Persisted model instance.
        **details: JSON-compatible commercial/technical facts, without secrets.
    """
    DomainEvent.objects.create(
        kind=kind, entity_type=entity._meta.model_name, entity_id=str(entity.pk), details=details,
    )

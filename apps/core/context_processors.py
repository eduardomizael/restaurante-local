from runtime.state import state
from apps.configuration.selectors import application_configuration


def application_identity(request):
    """Expose the saved display name and the current navigation area."""
    name = request.resolver_match.url_name if request.resolver_match else None
    return {
        "application_name": application_configuration().display_name,
        "is_configuration_page": name in {
            "application_configuration", "numbering", "document_configuration", "equipment_configuration",
        },
    }


def runtime_mode(request):
    """Expose technical mode without opening hardware or querying the database."""
    return {"runtime_mode": state.snapshot()}

from runtime.state import state
from apps.configuration.selectors import application_configuration


def application_identity(request):
    """Expose the saved display name and the current navigation area."""
    name = request.resolver_match.url_name if request.resolver_match else None
    area = "home"
    for route, pages in {
        "catalogue": {"catalogue", "new_product", "edit_product", "update_product_flag"},
        "report_orders": {"print_history", "saved_document", "reprint_document", "print_jobs_fragment",
                          "report_orders", "report_totals", "report_print", "report_print_result"},
        "application_configuration": {
            "application_configuration", "numbering", "document_configuration", "equipment_configuration",
        },
        "status": {"status", "status_fragment", "shutdown_confirmation", "shutdown"},
    }.items():
        if name in pages:
            area = route
            break
    return {
        "application_name": application_configuration().display_name,
        "main_navigation_area": area,
    }


def runtime_mode(request):
    """Expose technical mode without opening hardware or querying the database."""
    return {"runtime_mode": state.snapshot()}

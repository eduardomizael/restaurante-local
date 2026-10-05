from django.urls import path

from apps.core import views
from apps.orders import views as order_views
from apps.products import views as product_views
from apps.printing import views as print_views
from apps.configuration import views as configuration_views

urlpatterns = [
    path("", order_views.attendance, name="home"),
    path("board/fragment/", order_views.board_fragment, name="board_fragment"),
    path("board/products/", order_views.product_choices, name="product_choices"),
    path("products/", product_views.catalogue, name="catalogue"),
    path("products/new/", product_views.edit_product, name="new_product"),
    path("products/<int:product_id>/edit/", product_views.edit_product, name="edit_product"),
    path("products/<int:product_id>/flags/", product_views.update_flag, name="update_product_flag"),
    path("orders/new/", order_views.create_order, name="create_order"),
    path("orders/<int:order_id>/products/<int:product_id>/add/", order_views.manual_item, name="manual_item"),
    path("orders/measurements/add/", order_views.consume_measurement, name="consume_measurement"),
    path("orders/items/remove/", order_views.delete_item, name="delete_item"),
    path("orders/<int:order_id>/cancel/", order_views.confirm_cancel, name="confirm_cancel"),
    path("measurements/<int:measurement_id>/discard/", order_views.confirm_discard, name="confirm_discard"),
    path("numbering/", order_views.numbering, name="numbering"),
    path("configuration/", configuration_views.general, name="application_configuration"),
    path("configuration/document/", print_views.configuration, name="document_configuration"),
    path("configuration/equipment/", configuration_views.equipment, name="equipment_configuration"),
    path("orders/<int:order_id>/preview/", print_views.preview, name="print_preview"),
    path("orders/<int:order_id>/finalize/", print_views.finalize, name="finalize_order"),
    path("orders/<int:order_id>/print/", print_views.print_open, name="print_open_order"),
    path("printing/documents/<int:document_id>/", print_views.saved_document, name="saved_document"),
    path("printing/history/", print_views.history, name="print_history"),
    path("printing/<int:document_id>/jobs/", print_views.job_fragment, name="print_jobs_fragment"),
    path("printing/<int:document_id>/reprint/", print_views.reprint, name="reprint_document"),
    path("status/", views.status_page, name="status"),
    path("status/fragment/", views.status_fragment, name="status_fragment"),
    path("health/", views.health, name="health"),
    path("runtime/pause/", views.toggle_pause, name="toggle_pause"),
    path("runtime/shutdown/confirm/", views.shutdown_confirmation, name="shutdown_confirmation"),
    path("runtime/shutdown/", views.shutdown, name="shutdown"),
    path("assets/<str:name>", views.asset, name="asset"),
]

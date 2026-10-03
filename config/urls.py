from django.urls import path

from apps.core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("status/", views.status_page, name="status"),
    path("status/fragment/", views.status_fragment, name="status_fragment"),
    path("health/", views.health, name="health"),
    path("runtime/pause/", views.toggle_pause, name="toggle_pause"),
    path("assets/<str:name>", views.asset, name="asset"),
]

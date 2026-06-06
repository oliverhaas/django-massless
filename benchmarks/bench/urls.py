from django.urls import path

from . import views

urlpatterns = [
    path("", views.root),
    path("sync", views.sync_root),
    path("1k-json", views.json_1k),
    path("10k-json", views.json_10k),
    path("sync-10k-json", views.sync_json_10k),
    path("100k-json", views.json_100k),
    path("items/<int:item_id>", views.read_item),
    path("plaintext", views.plaintext),
    path("html", views.html),
    path("redirect", views.redirect),
    path("fast-root", views.fast_root),
    path("fast-1k-json", views.fast_json_1k),
    path("fast-10k-json", views.fast_json_10k),
    path("fast-plaintext", views.fast_plaintext),
]

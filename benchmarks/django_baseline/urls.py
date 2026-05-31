from django.urls import path

from . import views

urlpatterns = [
    path("", views.root),
    path("10k-json", views.ten_k_json),
    path("items/<int:item_id>", views.read_item),
]

from django.contrib import admin
from django.urls import path, re_path

from redirects import views

urlpatterns = [
    path("", views.home_page, name="home_page"),
    path("admin", views.admin_root, name="admin_root_no_slash"),
    path("admin/", admin.site.urls),
    path("healthz", views.healthz, name="healthz"),
    re_path(r"^(?P<source_path>.+)$", views.public_redirect, name="public_redirect"),
]

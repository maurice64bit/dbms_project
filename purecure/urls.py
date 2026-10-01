from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("records/<slug:table_name>/", views.records, name="records"),
    path("records/<slug:table_name>/<int:pk>/edit/", views.edit_record, name="edit_record"),
    path("records/<slug:table_name>/add/", views.add_record, name="add_record"),
    path("purchases/new/", views.record_purchase, name="record_purchase"),
    path("sales/new/", views.record_sale, name="record_sale"),
    path("sales/<int:sale_id>/receipt/", views.sale_receipt, name="sale_receipt"),
    path("sales/<int:sale_id>/payment/", views.take_payment, name="take_payment"),
]

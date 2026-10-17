from django.urls import path

from . import views

urlpatterns = [
    path("", views.board, name="board"),
    path("factura/<str:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("reglas/", views.rules, name="rules"),
    path("aprobaciones/", views.inbox, name="inbox"),
    path("aprobaciones/<int:record_id>/", views.decide_approval, name="decide_approval"),
    path("registro/", views.log, name="log"),
    path("demo/reiniciar/", views.reset_demo, name="reset_demo"),
    path("api/evaluate", views.api_evaluate, name="api_evaluate"),
]

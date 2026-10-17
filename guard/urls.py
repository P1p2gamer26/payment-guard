from django.urls import path

from . import views

urlpatterns = [
    path("", views.board, name="board"),
    path("biblioteca/", views.library, name="library"),
    path("factura/<str:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("factura/<str:invoice_id>/alterar/", views.tamper_receipt, name="tamper_receipt"),
    path("factura/<str:invoice_id>/corregir/", views.corregir_campo, name="corregir_campo"),
    path("arena/correr/", views.correr_arena, name="correr_arena"),
    path("reglas/mandato-v2/", views.aplicar_mandato_v2, name="aplicar_mandato_v2"),
    path("reglas/", views.rules, name="rules"),
    path("aprobaciones/", views.inbox, name="inbox"),
    path("aprobaciones/<int:record_id>/", views.decide_approval, name="decide_approval"),
    path("registro/", views.log, name="log"),
    path("demo/reiniciar/", views.reset_demo, name="reset_demo"),
    path("api/evaluate", views.api_evaluate, name="api_evaluate"),
    path("api/eventos", views.api_eventos, name="api_eventos"),
    path("demo/en-vivo/", views.demo_en_vivo, name="demo_en_vivo"),
    path("demo/en-vivo/siguiente/", views.demo_en_vivo_siguiente, name="demo_en_vivo_siguiente"),
]

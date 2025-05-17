from django.urls import path
from .views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', staff_login, name='staff_login'),
    path('dashboard/', staff_dashboard, name='staff_dashboard'),
    path('products/', product_list, name='product_list'),
    path('shops/', shop_list, name='shop_list'),
    path('shop-products/', shop_product_list, name='shop_product_list'),
    path('logout/', staff_logout, name='staff_logout'),
    
    
    
    #sales urls
    path('create-sale/', create_sale_view, name='create_sale'),
    path('api/shop-products/<int:shop_id>/', get_shop_products, name='get_shop_products'),
    path('api/submit-sale/', submit_sale, name='submit_sale'),
    path('sales/', sale_list_view, name='sale_list'),
    path('sales/<int:sale_id>/invoice/', sale_invoice_pdf, name='sale_invoice_pdf'),
    
    path('sales/shop/<int:shop_id>/', shop_sales_view, name='shop_sales'),
    path('sales/shop/<int:shop_id>/advance/', record_advance_payment, name='record_advance_payment'),
    path('all-sales/', all_sales_view, name='all_sales'),
    path('sales-report/', sales_report, name='sales_report'),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
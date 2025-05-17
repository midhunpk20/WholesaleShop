from django.contrib import admin
from .models import Product,Dealer,Shop,ShopProduct

# Register your models here.

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_price')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 10  
    exclude = ('added_by',)  # Hide from form

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only set when adding
            obj.added_by = request.user
        obj.save()
        
admin.site.register(Product, ProductAdmin)

class DealerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'email')
    search_fields = ('user__username', 'phone', 'email')
    list_filter = ('user__is_staff',)
    ordering = ('user__username',)
    list_per_page = 10    
admin.site.register(Dealer, DealerAdmin)

class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'phone', 'email', 'balance')
    search_fields = ('name', 'location', 'phone', 'email')
    list_filter = ('balance',)
    ordering = ('name',)
    list_per_page = 10
    readonly_fields = ('balance',)  # Make balance read-only in the form
admin.site.register(Shop, ShopAdmin)

class ShopProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'shop', 'custom_price')
    search_fields = ('product__name', 'shop__name')
    list_filter = ('shop',)
    ordering = ('product',)
    list_per_page = 10
admin.site.register(ShopProduct, ShopProductAdmin)
# Register the models with the admin site   
        
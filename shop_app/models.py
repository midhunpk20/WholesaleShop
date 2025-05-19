
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


#Dealer model
class Dealer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'is_staff': True})
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.user.username

# Product model
class Product(models.Model):
    name = models.CharField(max_length=255)
    default_price = models.DecimalField(max_digits=10, decimal_places=2)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

# Shop model
class Shop(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return self.name

    def get_product_prices(self):
        """
        Returns a list of prices (custom if set, otherwise default) for all products assigned to this shop.
        """
        shop_products = ShopProduct.objects.filter(shop=self).select_related('product')
        return [sp.get_price() for sp in shop_products]

# ShopProduct model - links products to shops
class ShopProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        unique_together = ('product', 'shop')

    def get_price(self):
        """
        Returns the custom price if available, else the product's default price.
        """
        return self.custom_price if self.custom_price is not None else self.product.default_price

    def __str__(self):
        return f"{self.shop.name} - {self.product.name}"    
    
class Sale(models.Model):
    """Model to represent a complete sale transaction"""
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    # Payment status options
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partially Paid'),
    ]
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    def __str__(self):
        return f"Sale #{self.id} - {self.shop.name} - {self.date_created.strftime('%Y-%m-%d %H:%M')}"
    
    def calculate_total(self):
        """Calculate the total amount based on all sale items"""
        total = sum(item.subtotal for item in self.saleitems.all())
        self.total_amount = total
        self.save() 
        return total
    
    def update_shop_balance(self):
        """Update shop balance based on payment"""
        self.shop.balance += self.amount_paid
        self.shop.save()
    
    def record_payment(self, amount):
        """Record a payment against this sale"""
        self.amount_paid += Decimal(amount)
        
        # Update payment status based on amount paid
        if self.amount_paid >= self.total_amount:
            self.payment_status = 'PAID'
        elif self.amount_paid > 0:
            self.payment_status = 'PARTIAL'
        
        self.save()
        self.update_shop_balance()


class SaleItem(models.Model):
    """Model to represent individual items in a sale"""
    sale = models.ForeignKey(Sale, related_name='saleitems', on_delete=models.CASCADE)
    shop_product = models.ForeignKey('ShopProduct', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of sale
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.quantity} x {self.shop_product.product.name}"
        
    def save(self, *args, **kwargs):
        if not self.price:
            self.price = self.shop_product.get_price()
        self.subtotal = self.price * self.quantity
        super().save(*args, **kwargs)
        self.sale.calculate_total() 
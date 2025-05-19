from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Product, Shop, ShopProduct,Sale,SaleItem
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
import json
from django.template.loader import get_template
from xhtml2pdf import pisa
import io
from decimal import Decimal,InvalidOperation
from django.db import models,transaction
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.templatetags.static import static



def is_staff(user):
    return user.is_authenticated and user.is_staff

def staff_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('staff_dashboard')
        else:
            messages.error(request, 'Invalid credentials or not a staff member')
    return render(request, 'staff_app/login.html')



@login_required
@user_passes_test(lambda u: u.is_staff)
def staff_dashboard(request):
    shop_count = Shop.objects.count()
    product_count = Product.objects.count()
    total_sold_quantity = SaleItem.objects.aggregate(total=models.Sum('quantity'))['total'] or 0

    context = {
        'shop_count': shop_count,
        'product_count': product_count,
        'total_sold_quantity': total_sold_quantity,
    }
    return render(request, 'staff_app/dashboard.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_list(request):
    search_query = request.GET.get('search', '')
    
    products = Product.objects.all().order_by('name')
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)  # ✅ Only filter by name
        )
    
    paginator = Paginator(products, 10)  # Show 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    return render(request, 'staff_app/product_list.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def shop_list(request):
    shops = Shop.objects.all().order_by('name')
    paginator = Paginator(shops, 10)  # Show 10 shops per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'staff_app/shop_list.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def shop_product_list(request):
    selected_shop_id = request.GET.get('shop_id', 'all')
    search_query = request.GET.get('search', '')
    
    # Get all shops
    shops = Shop.objects.all().order_by('name')
    
    # Get and filter products by name
    products = Product.objects.all().order_by('name')
    if search_query:
        products = products.filter(name__icontains=search_query)
    
    # Get existing shop-product relationships
    shop_products = ShopProduct.objects.all().select_related('shop', 'product')
    
    # Create lookup dictionary for existing shop-product relationships
    shop_product_dict = {(sp.shop_id, sp.product_id): sp for sp in shop_products}
    
    # Generate comprehensive list including both existing and potential shop-products
    all_items = []
    
    # If filtering by a specific shop
    if selected_shop_id != 'all':
        shop = shops.get(id=selected_shop_id)
        for product in products:
            existing = shop_product_dict.get((shop.id, product.id))
            if existing:
                all_items.append(existing)
            else:
                # Create a temporary object for products not yet assigned to this shop
                temp_item = {
                    'shop': shop,
                    'product': product,
                    'custom_price': None
                }
                all_items.append(temp_item)
    else:
        # When showing all shops, only include existing shop-product relationships
        # to avoid an excessively large list
        filtered_shop_products = shop_products
        if search_query:
            product_ids = products.values_list('id', flat=True)
            filtered_shop_products = filtered_shop_products.filter(product_id__in=product_ids)
        all_items = list(filtered_shop_products)
    
    # Pagination
    paginator = Paginator(all_items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'shops': shops,
        'selected_shop_id': selected_shop_id,
        'search_query': search_query,
    }
    return render(request, 'staff_app/shop_product_list.html', context)


def staff_logout(request):
    logout(request)
    return redirect('staff_login')






#sell product

def create_sale_view(request):
    shops = Shop.objects.all()
    return render(request, 'sale/create_sale.html', {'shops': shops})


def get_shop_products(request, shop_id):
    # Get all products
    all_products = Product.objects.all()
    
    # Get shop products for this shop
    shop_products = ShopProduct.objects.filter(shop_id=shop_id).select_related('product')
    
    # Create a mapping of product_id to shop_product for quick lookup
    shop_product_map = {sp.product.id: sp for sp in shop_products}
    
    data = []
    for product in all_products:
        # Check if this product is associated with the shop
        if product.id in shop_product_map:
            shop_product = shop_product_map[product.id]
            price = float(shop_product.get_price())
            shop_product_id = shop_product.id
        else:
            # If not associated, use default price and mark shop_product_id as None
            price = float(product.default_price)
            shop_product_id = None
        
        data.append({
            'id': shop_product_id,
            'product_id': product.id,
            'product_name': product.name,
            'price': price,
            'is_in_shop': shop_product_id is not None
        })
    
    return JsonResponse({'products': data})


@csrf_exempt
def submit_sale(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        shop_id = data.get('shop_id')
        products = data.get('products')  # List of {product_id, quantity, price}
        discount_percent = Decimal(data.get('discount_percent', 0))
        discount_amount = Decimal(data.get('discount_amount', 0))

        if not shop_id:
            return JsonResponse({'status': 'error', 'message': 'No shop selected'}, status=400)
        if not products or len(products) == 0:
            return JsonResponse({'status': 'error', 'message': 'No products selected'}, status=400)

        try:
            shop = Shop.objects.get(id=shop_id)

            with transaction.atomic():
                sale = Sale.objects.create(
                    shop=shop,
                    discount_percent=discount_percent,
                    discount_amount=discount_amount
                )

                total_amount = Decimal('0.0')

                for item in products:
                    product_id = item.get('product_id')
                    shop_product_id = item.get('shop_product_id')
                    quantity = int(item['quantity'])
                    price = Decimal(item['price'])

                    if shop_product_id:
                        shop_product = ShopProduct.objects.get(id=shop_product_id)
                    else:
                        product = Product.objects.get(id=product_id)
                        shop_product, _ = ShopProduct.objects.get_or_create(
                            shop=shop,
                            product=product,
                            defaults={'custom_price': price if price != product.default_price else None}
                        )

                    subtotal = quantity * price

                    SaleItem.objects.create(
                        sale=sale,
                        shop_product=shop_product,
                        quantity=quantity,
                        price=price,
                        subtotal=subtotal
                    )
                    total_amount += subtotal

                # Apply discount percent (if any)
                if discount_percent > 0:
                    discount_value = (total_amount * discount_percent / Decimal('100.0')).quantize(Decimal('0.01'))
                    discount_amount += discount_value  # combine with manually added discount_amount

                total_after_discount = total_amount - discount_amount
                if total_after_discount < 0:
                    total_after_discount = Decimal('0.0')

                sale.discount_amount = discount_amount
                sale.total_amount = total_after_discount
                sale.save()

            return JsonResponse({'status': 'success', 'sale_id': sale.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)
#shop sales LISTING

def sale_list_view(request):
    """Show list of shops with their balance and view button"""
    shops = Shop.objects.all()
    return render(request, 'sale/sale_list.html', {'shops': shops})

def shop_sales_view(request, shop_id):
    shop = get_object_or_404(Shop, id=shop_id)

    sales = Sale.objects.filter(shop=shop).select_related('shop').prefetch_related(
        'saleitems__shop_product__product'
    ).order_by('-date_created')

    total_sales_amount = sum(sale.total_amount for sale in sales)
    
    # The shop.balance is the correct amount that's been paid
    current_paid_amount = shop.balance
    
    # Calculate remaining balance
    remaining_balance = total_sales_amount - current_paid_amount

    context = {
        'shop': shop,
        'sales': sales,
        'total_sales_amount': total_sales_amount,
        'current_paid_amount': current_paid_amount,
        'remaining_balance': remaining_balance,
    }
    return render(request, 'sale/shop_sales.html', context)

def record_advance_payment(request, shop_id):
    """Record an advance payment for a shop (as a Sale with amount_paid and no items)"""
    if request.method == 'POST':
        shop = get_object_or_404(Shop, id=shop_id)
        try:
            amount = Decimal(request.POST.get('amount', 0))
            if amount <= 0:
                messages.error(request, "Please enter a valid amount greater than zero.")
                return redirect('shop_sales', shop_id=shop_id)

            # Create a dummy sale with only amount_paid
            sale = Sale.objects.create(
                shop=shop,
                total_amount=0,  # No sale items
                amount_paid=amount,
                payment_status='PAID'
            )
            sale.update_shop_balance()

            messages.success(request, f"Advance payment of ₹{amount} recorded successfully.")
        except (ValueError, InvalidOperation):
            messages.error(request, "Please enter a valid amount.")

    return redirect('shop_sales', shop_id=shop_id)

def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("utf-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

def sale_invoice_pdf(request, sale_id):
    sale = get_object_or_404(Sale.objects.prefetch_related('saleitems__shop_product__product'), id=sale_id)
    
    # Calculate the remaining balance
    remaining_balance = sale.total_amount - sale.amount_paid
    logo_url = request.build_absolute_uri(static('images/logo.png'))
    
    context = {
        'sale': sale,
        'items': sale.saleitems.all(),
        'remaining_balance': remaining_balance,
        'logo_url': logo_url,
    }
    return render_to_pdf('sale/sale_invoice.html', context)


def all_sales_view(request):
    """View to list all sales"""
    # Get only sales that have at least one item
    sales = Sale.objects.annotate(
        items_count=models.Count('saleitems')
    ).filter(
        items_count__gt=0
    ).select_related('shop').prefetch_related(
        'saleitems__shop_product__product'
    ).order_by('-date_created')
    
    # Calculate total sales amount for valid sales only
    total_sales_amount = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    context = {
        'sales': sales,
        'total_sales_amount': total_sales_amount,
    }
    return render(request, 'sale/all_sales.html', context)

def sales_report(request):
    # 1. Products purchased by date
    products_by_date = (
        SaleItem.objects
        .annotate(date=TruncDate('sale__date_created'))
        .values('shop_product__product__name', 'date')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('-date')
    )


    # 2. Most purchased products
    most_purchased_products = (
        SaleItem.objects
        .values('shop_product__product__name')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('-total_quantity')[:10]
    )

    # 3. Most purchasing shops
    most_purchasing_shops = (
        Sale.objects
        .values('shop__name')
        .annotate(total_purchased=Sum('total_amount'))
        .order_by('-total_purchased')[:10]
    )

    context = {
        'products_by_date': products_by_date,
        'most_purchased_products': most_purchased_products,
        'most_purchasing_shops': most_purchasing_shops,
    }

    return render(request, 'sale/sales_report.html', context)
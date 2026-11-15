"""Views for the agricultural marketplace."""

from decimal import Decimal, InvalidOperation
import logging
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from common import validate_image_upload, validate_video_upload
from .models import Order, OrderItem, ProduceListing

logger = logging.getLogger(__name__)
HOMEPAGE_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _homepage_images() -> list[dict[str, str]]:
    """Return raster image assets available for the homepage gallery."""
    images_dir = Path(__file__).resolve().parents[2] / 'frontend' / 'static' / 'images'
    images = []
    for image_path in sorted(images_dir.rglob('*'), key=lambda path: str(path).lower()):
        if image_path.is_file() and image_path.suffix.lower() in HOMEPAGE_IMAGE_EXTENSIONS:
            relative_path = image_path.relative_to(images_dir).as_posix()
            images.append({
                'url': f'images/{relative_path}',
                'alt': image_path.stem.replace('_', ' ').replace('-', ' '),
            })
    return images


def _validation_error_message(error: ValidationError) -> str:
    return ' '.join(error.messages)


def _validate_price(price_str: str) -> Decimal:
    try:
        price = Decimal(price_str)
        if not price.is_finite() or price <= 0:
            raise ValidationError('Price must be greater than zero.')
        if price > Decimal('999999.99'):
            raise ValidationError('Price is too large.')
        if price.as_tuple().exponent < -2:
            raise ValidationError('Price can include at most 2 decimal places.')
        return price
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValidationError('Price must be a valid number.') from error


def _validate_quantity(quantity_str: str) -> str:
    if not quantity_str or len(quantity_str) > 50:
        raise ValidationError('Quantity must be provided and less than 50 characters.')
    return quantity_str.strip()


def _is_farmer(user) -> bool:
    return user.is_staff or getattr(getattr(user, 'profile', None), 'role', None) == 'farmer'


def _is_buyer(user) -> bool:
    return getattr(getattr(user, 'profile', None), 'role', None) == 'buyer'


@require_http_methods(['GET'])
def market_feed(request: HttpRequest) -> HttpResponse:
    listings = ProduceListing.objects.filter(
        is_available=True
    ).order_by('-created_at').select_related('seller')
    return render(request, 'marketplace/feed.html', {
        'listings': listings,
        'homepage_images': _homepage_images(),
    })


@require_http_methods(['GET'])
def farmer_directory(request: HttpRequest) -> HttpResponse:
    farmers = (
        ProduceListing.objects.filter(
            is_available=True, seller__profile__role='farmer'
        )
        .values('seller__username', 'seller_id')
        .distinct()
    )
    return render(request, 'marketplace/farmer_directory.html', {'farmers': farmers})


@require_http_methods(['GET'])
def farmer_listings(request: HttpRequest, username: str) -> HttpResponse:
    listings = ProduceListing.objects.filter(
        seller__username=username,
        seller__profile__role='farmer',
        is_available=True,
    ).select_related('seller')
    if not listings.exists():
        raise Http404('Farmer not found.')
    return render(request, 'marketplace/farmer_listings.html', {
        'farmer': listings.first().seller,
        'listings': listings,
    })


@require_http_methods(['GET'])
def listing_detail(request: HttpRequest, pk: int) -> HttpResponse:
    listing = get_object_or_404(ProduceListing, pk=pk, is_available=True)
    return render(request, 'marketplace/detail.html', {'listing': listing})


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def create_listing(request: HttpRequest) -> HttpResponse:
    if not _is_farmer(request.user):
        messages.error(request, 'Only farmer accounts can post produce.')
        return redirect('market_feed')

    form_data = {
        key: '' for key in (
            'title', 'description', 'price', 'quantity',
            'village_origin', 'target_town',
        )
    }
    if request.method == 'POST':
        form_data = {key: request.POST.get(key, '').strip() for key in form_data}
        title = form_data['title']
        description = form_data['description']
        image = request.FILES.get('camera_image') or request.FILES.get('image')
        video = request.FILES.get('camera_video') or request.FILES.get('video')

        if not all(form_data.values()):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'marketplace/create_listing.html', {'form_data': form_data})
        if len(title) > 200:
            messages.error(request, 'Title must be less than 200 characters.')
            return render(request, 'marketplace/create_listing.html', {'form_data': form_data})
        if len(description) > 2000:
            messages.error(request, 'Description must be less than 2000 characters.')
            return render(request, 'marketplace/create_listing.html', {'form_data': form_data})
        if len(form_data['village_origin']) > 100 or len(form_data['target_town']) > 100:
            messages.error(request, 'Village and target town must be less than 100 characters.')
            return render(request, 'marketplace/create_listing.html', {'form_data': form_data})

        try:
            price = _validate_price(form_data['price'])
            quantity = _validate_quantity(form_data['quantity'])
            validate_image_upload(image)
            validate_video_upload(video)
            with transaction.atomic():
                ProduceListing.objects.create(
                    seller=request.user,
                    title=title,
                    description=description,
                    price=price,
                    quantity=quantity,
                    village_origin=form_data['village_origin'],
                    target_town=form_data['target_town'],
                    image=image,
                    video=video,
                )
            messages.success(request, 'Listing created successfully!')
            return redirect('market_feed')
        except ValidationError as error:
            messages.error(request, _validation_error_message(error))
        except DatabaseError:
            logger.exception('Database error while creating listing for user %s', request.user.pk)
            messages.error(request, 'We could not save your listing right now. Please try again.')
    return render(request, 'marketplace/create_listing.html', {'form_data': form_data})


@login_required(login_url='login')
@require_http_methods(['POST'])
def add_to_cart(request: HttpRequest, pk: int) -> HttpResponse:
    if not _is_buyer(request.user):
        messages.error(request, 'Only buyer accounts can place orders.')
        return redirect('listing_detail', pk=pk)
    listing = get_object_or_404(ProduceListing, pk=pk, is_available=True)
    try:
        quantity = int(request.POST.get('quantity', '1'))
    except ValueError:
        quantity = 0
    if quantity < 1:
        messages.error(request, 'Quantity must be at least 1.')
        return redirect('listing_detail', pk=pk)
    cart_data = request.session.setdefault('cart', {})
    key = str(pk)
    cart_data[key] = int(cart_data.get(key, 0)) + quantity
    request.session['cart'] = cart_data
    request.session.modified = True
    messages.success(request, f'{listing.title} was added to your cart.')
    return redirect('cart')


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def cart(request: HttpRequest) -> HttpResponse:
    if not _is_buyer(request.user):
        messages.error(request, 'Only buyer accounts can place orders.')
        return redirect('market_feed')
    cart_data = request.session.get('cart', {})
    listings = ProduceListing.objects.filter(
        pk__in=cart_data.keys(), is_available=True
    ).select_related('seller')
    items = []
    total = Decimal('0')
    for listing in listings:
        quantity = int(cart_data.get(str(listing.pk), 0))
        if quantity > 0:
            subtotal = listing.price * quantity
            items.append({'listing': listing, 'quantity': quantity, 'subtotal': subtotal})
            total += subtotal
    if request.method == 'POST':
        if not items:
            messages.error(request, 'Your cart is empty.')
            return redirect('cart')
        with transaction.atomic():
            order = Order.objects.create(buyer=request.user, total=total)
            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    listing=item['listing'],
                    quantity=item['quantity'],
                    unit_price=item['listing'].price,
                ) for item in items
            ])
        request.session['cart'] = {}
        messages.success(request, f'Order #{order.pk} placed successfully.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'marketplace/cart.html', {'items': items, 'total': total})


@login_required(login_url='login')
@require_http_methods(['GET'])
def order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.prefetch_related('items__listing'),
        pk=pk,
        buyer=request.user,
    )
    return render(request, 'marketplace/order_detail.html', {'order': order})

"""
Marketplace models for agricultural produce listings.

This module defines the data structure for produce listings in the
agricultural marketplace platform.
"""

from django.db import models
from django.contrib.auth.models import User


class ProduceListing(models.Model):
    """
    Represents a produce listing posted by a farmer/seller.
    
    This model stores all relevant information about agricultural products
    available for sale, including location information, pricing, and
    seller details through foreign key relationship.
    
    Attributes:
        seller (ForeignKey): The farmer/seller posting the listing
        title (str): Product name/title (max 200 chars)
        description (str): Detailed product description
        price (Decimal): Price in local currency
        quantity (str): Quantity and unit (e.g., "50kg bag")
        image (ImageField): Product photo
        video (FileField): Short product video
        village_origin (str): Village where produce is located
        target_town (str): Nearest town/destination
        created_at (DateTime): Timestamp when listing was created
        is_available (bool): Whether listing is still active
    """

    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='listings',
        help_text='Farmer or seller who posted this listing'
    )

    title = models.CharField(
        max_length=200,
        help_text='e.g., Organic sweet potatoes, Fresh Tomatoes'
    )
    
    description = models.TextField(
        help_text='Detailed description of the produce'
    )
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Price in local currency'
    )
    
    quantity = models.CharField(
        max_length=50,
        help_text='e.g., 50kg bag, 1 crate'
    )
    
    image = models.ImageField(
        upload_to='listings/',
        null=True,
        blank=True,
        help_text='Upload a photo of your produce'
    )

    video = models.FileField(
        upload_to='listing_videos/',
        null=True,
        blank=True,
        help_text='Upload a short video of your harvest'
    )

    village_origin = models.CharField(
        max_length=100,
        help_text='Village where the produce is located'
    )
    
    target_town = models.CharField(
        max_length=100,
        help_text='Nearest town'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Creation timestamp'
    )
    
    is_available = models.BooleanField(
        default=True,
        help_text='Whether this listing is currently active'
    )

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self.title} - {self.village_origin} to {self.target_town}"

    class Meta:
        """Model metadata configuration."""
        ordering = ['-created_at']
        verbose_name_plural = 'Produce Listings'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_available']),
        ]


class Order(models.Model):
    """A buyer's order containing one or more produce listings."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    buyer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='produce_orders'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Order #{self.pk} by {self.buyer.username}'


class OrderItem(models.Model):
    """A listing and quantity captured at the time an order is placed."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey(
        ProduceListing, on_delete=models.PROTECT, related_name='order_items'
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

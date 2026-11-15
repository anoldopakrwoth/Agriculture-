# marketplace/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.market_feed, name='market_feed'),
    path('farmers/', views.farmer_directory, name='farmer_directory'),
    path('farmers/<str:username>/', views.farmer_listings, name='farmer_listings'),
    path('listing/new/', views.create_listing, name='create_listing'),
    path('listing/<int:pk>/', views.listing_detail, name='listing_detail'),
    path('listing/<int:pk>/cart/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart, name='cart'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
]
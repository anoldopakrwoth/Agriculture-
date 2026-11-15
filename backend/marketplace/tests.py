from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Order, ProduceListing


class CreateListingValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='farmer',
            password='Password123',
        )
        self.user.profile.role = 'farmer'
        self.user.profile.save()
        self.valid_payload = {
            'title': 'Fresh Tomatoes',
            'description': 'Good quality tomatoes',
            'price': '5000.00',
            'quantity': '1 crate',
            'village_origin': 'Mukono',
            'target_town': 'Kampala',
        }

    def test_invalid_price_does_not_create_listing(self):
        self.client.force_login(self.user)
        payload = {**self.valid_payload, 'price': 'not-a-number'}

        response = self.client.post(reverse('create_listing'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Price must be a valid number.')
        self.assertFalse(ProduceListing.objects.exists())

    def test_invalid_image_type_does_not_create_listing(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            'not-image.txt',
            b'plain text',
            content_type='text/plain',
        )
        payload = {**self.valid_payload, 'image': upload}

        response = self.client.post(reverse('create_listing'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Only JPEG, PNG, GIF, and WebP images are allowed.')
        self.assertFalse(ProduceListing.objects.exists())

    def test_valid_listing_is_created(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('create_listing'),
            self.valid_payload,
        )

        self.assertRedirects(response, reverse('market_feed'))
        listing = ProduceListing.objects.get()
        self.assertEqual(listing.seller, self.user)
        self.assertEqual(listing.title, 'Fresh Tomatoes')

    def test_missing_field_keeps_entered_values(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('create_listing'),
            {**self.valid_payload, 'description': ''},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fresh Tomatoes')
        self.assertContains(response, 'Please fill in all required fields.')
        self.assertFalse(ProduceListing.objects.exists())

    def test_buyer_cannot_create_listing(self):
        self.user.profile.role = 'buyer'
        self.user.profile.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse('create_listing'))

        self.assertRedirects(response, reverse('market_feed'))
        self.assertFalse(ProduceListing.objects.exists())

    def test_media_files_are_limited_to_ten_mb_each(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            'large.jpg',
            b'x' * (10 * 1024 * 1024 + 1),
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('create_listing'),
            {**self.valid_payload, 'image': upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Image size must not exceed 10MB.')
        self.assertFalse(ProduceListing.objects.exists())


class CartAndOrderTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(username='farmer', password='Password123')
        self.farmer.profile.role = 'farmer'
        self.farmer.profile.save()
        self.buyer = User.objects.create_user(username='buyer', password='Password123')
        self.listing = ProduceListing.objects.create(
            seller=self.farmer,
            title='Maize',
            description='Fresh maize',
            price='1200.00',
            quantity='1 bag',
            village_origin='Mbale',
            target_town='Kampala',
        )

    def test_buyer_can_add_listing_to_cart_and_place_order(self):
        self.client.force_login(self.buyer)
        add_response = self.client.post(
            reverse('add_to_cart', args=[self.listing.pk]),
            {'quantity': 2},
        )
        self.assertRedirects(add_response, reverse('cart'))

        response = self.client.post(reverse('cart'))

        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_detail', args=[order.pk]))
        self.assertEqual(order.total, 2400)
        self.assertEqual(order.items.get().quantity, 2)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('marketplace', '0006_producelisting_video'),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('buyer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='produce_orders', to='auth.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='order_items', to='marketplace.producelisting')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='marketplace.order')),
            ],
        ),
    ]

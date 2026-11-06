import factory
from django.utils import timezone
from apps.accounts.models import User
from apps.catalog.models import Category, Item
from apps.core.constants import CATEGORY_GROUPS, ItemStatus


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    phone = factory.Sequence(lambda n: f"09000000{n:02d}")
    full_name = factory.Faker("name", locale="vi_VN")
    building = "S1"
    unit_number = factory.Sequence(lambda n: f"{n + 100}")
    is_resident_verified = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        manager = cls._get_manager(model_class)
        return manager.create_user(**kwargs)


class AdminFactory(UserFactory):
    is_staff = True
    phone = factory.Sequence(lambda n: f"09999999{n:02d}")


class UnverifiedUserFactory(UserFactory):
    is_resident_verified = False
    phone = factory.Sequence(lambda n: f"09111111{n:02d}")


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")
    group = CATEGORY_GROUPS[0][0]


class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Item {n}")
    category = factory.SubFactory(CategoryFactory)
    retail_price = 1_000_000
    daily_price = 70_000
    deposit_tier = 200_000
    building = factory.LazyAttribute(lambda o: o.owner.building)
    status = ItemStatus.ACTIVE

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Generate a placeholder image for photo_1
        from PIL import Image
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile

        if "photo_1" not in kwargs or not kwargs["photo_1"]:
            img = Image.new("RGB", (100, 100), color="blue")
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            buf.seek(0)
            kwargs["photo_1"] = SimpleUploadedFile("test.jpg", buf.read(), content_type="image/jpeg")

        return super()._create(model_class, *args, **kwargs)


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "orders.Order"

    item = factory.SubFactory(ItemFactory)
    renter = factory.SubFactory(UserFactory, building="S1")
    owner = factory.LazyAttribute(lambda o: o.item.owner)
    rental_duration = "24h"
    pickup_slot = "morning"
    pickup_time = factory.LazyFunction(timezone.now)
    daily_price = 70_000
    rental_fee = 70_000
    deposit = 200_000
    platform_fee = 5_000
    total_amount = 275_000
    commission = 10_500
    owner_payout = 59_500
    risk_fund = 620


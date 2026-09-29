from rest_framework import serializers
from django.db import transaction
from .models import Library, PricingPlan
from apps.seats.models import Seat


class PricingPlanSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PricingPlan
        fields = ["id", "name", "duration_days", "price", "created_at"]
        read_only_fields = ["id", "created_at"]


class LibrarySerializer(serializers.ModelSerializer):
    owner_id = serializers.UUIDField(source="owner.id", read_only=True)
    owner_name = serializers.CharField(source="owner.name", read_only=True)
    plans = PricingPlanSerializer(many=True, read_only=True)
    domains = serializers.ListField(source="domains_list", read_only=True)
    seat_summary = serializers.SerializerMethodField()

    class Meta:
        model = Library
        fields = [
            "id",
            "owner_id",
            "owner_name",
            "name",
            "address",
            "latitude",
            "longitude",
            "contact_phone",
            "contact_email",
            "total_seats",
            "opens_at",
            "closes_at",
            "operating_hours",
            "domains_catered",
            "domains",
            "plans",
            "seat_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner_id", "owner_name", "created_at", "updated_at"]

    def get_seat_summary(self, obj):
        seats = Seat.objects.filter(library=obj)
        total = seats.count()
        empty = seats.filter(status="empty").count()
        reserved = seats.filter(status="reserved").count()
        occupied = seats.filter(status="occupied").count()
        return {
            "total": total if total > 0 else obj.total_seats,
            "empty": empty,
            "reserved": reserved,
            "occupied": occupied,
        }


class LibraryCreateUpdateSerializer(serializers.ModelSerializer):
    pricing_plans = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
    )
    initial_seats = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
    )
    seat_layout = serializers.DictField(
        required=False,
        write_only=True,
    )

    class Meta:
        model = Library
        fields = [
            "id",
            "name",
            "address",
            "latitude",
            "longitude",
            "contact_phone",
            "contact_email",
            "total_seats",
            "opens_at",
            "closes_at",
            "operating_hours",
            "domains_catered",
            "pricing_plans",
            "initial_seats",
            "seat_layout",
        ]
        read_only_fields = ["id"]

    def validate_domains_catered(self, value):
        if isinstance(value, list):
            return ",".join(str(v).strip() for v in value if str(v).strip())
        return value

    def to_internal_value(self, data):
        # Allow domains_catered to be passed as an array
        if "domains_catered" in data and isinstance(data["domains_catered"], list):
            data = data.copy()
            data["domains_catered"] = ",".join(str(v).strip() for v in data["domains_catered"] if str(v).strip())
        return super().to_internal_value(data)

    def create(self, validated_data):
        pricing_plans_data = validated_data.pop("pricing_plans", [])
        initial_seats_data = validated_data.pop("initial_seats", [])
        seat_layout_data = validated_data.pop("seat_layout", None)
        request = self.context.get("request")

        with transaction.atomic():
            library = Library.objects.create(owner=request.user, **validated_data)

            # Create pricing plans
            for plan_data in pricing_plans_data:
                PricingPlan.objects.create(
                    library=library,
                    name=plan_data.get("name", "Standard"),
                    duration_days=int(plan_data.get("duration_days", 30)),
                    price=plan_data.get("price", 0),
                )

            # Create initial seats if provided
            seats_to_create = []
            if initial_seats_data:
                for s in initial_seats_data:
                    label = s.get("label")
                    if label:
                        seats_to_create.append(Seat(
                            library=library,
                            label=label,
                            status=s.get("status", "empty"),
                        ))
            elif seat_layout_data:
                rows = seat_layout_data.get("rows", [])
                seats_per_row = int(seat_layout_data.get("seats_per_row", 0))
                for row in rows:
                    for num in range(1, seats_per_row + 1):
                        seats_to_create.append(Seat(
                            library=library,
                            label=f"Row {row} - Seat {num}",
                            status="empty",
                        ))

            if seats_to_create:
                Seat.objects.bulk_create(seats_to_create, ignore_conflicts=True)
                library.total_seats = len(seats_to_create)
                library.save(update_fields=["total_seats", "updated_at"])

            return library

    def update(self, instance, validated_data):
        pricing_plans_data = validated_data.pop("pricing_plans", None)
        initial_seats_data = validated_data.pop("initial_seats", None)
        seat_layout_data = validated_data.pop("seat_layout", None)

        with transaction.atomic():
            for attr, val in validated_data.items():
                setattr(instance, attr, val)
            instance.save()

            if pricing_plans_data is not None:
                instance.plans.all().delete()
                for plan_data in pricing_plans_data:
                    PricingPlan.objects.create(
                        library=instance,
                        name=plan_data.get("name", "Standard"),
                        duration_days=int(plan_data.get("duration_days", 30)),
                        price=plan_data.get("price", 0),
                    )

            if initial_seats_data is not None:
                for s in initial_seats_data:
                    label = s.get("label")
                    if label:
                        Seat.objects.update_or_create(
                            library=instance,
                            label=label,
                            defaults={"status": s.get("status", "empty")},
                        )
                instance.total_seats = Seat.objects.filter(library=instance).count()
                instance.save(update_fields=["total_seats", "updated_at"])
            elif seat_layout_data:
                rows = seat_layout_data.get("rows", [])
                seats_per_row = int(seat_layout_data.get("seats_per_row", 0))
                for row in rows:
                    for num in range(1, seats_per_row + 1):
                        Seat.objects.update_or_create(
                            library=instance,
                            label=f"Row {row} - Seat {num}",
                            defaults={"status": "empty"},
                        )
                instance.total_seats = Seat.objects.filter(library=instance).count()
                instance.save(update_fields=["total_seats", "updated_at"])

            return instance

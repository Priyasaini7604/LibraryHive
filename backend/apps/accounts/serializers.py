"""Input validation and output shapes for accounts. No side effects here."""

from rest_framework import serializers

from apps.core.serializers import DomainSerializer

from .models import User


class RegisterInput(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)
    name = serializers.CharField(min_length=2, max_length=150, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)
    domain_code = serializers.CharField(max_length=40, required=False, allow_blank=True)


class LoginInput(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class ProfileUpdateInput(serializers.Serializer):
    """Email is deliberately not editable (BACKEND_ARCHITECTURE.md #11)."""

    name = serializers.CharField(min_length=2, max_length=150, required=False)
    phone = serializers.CharField(max_length=32, required=False)
    domain_code = serializers.CharField(max_length=40, required=False, allow_blank=True, allow_null=True)


class UserSerializer(serializers.ModelSerializer):
    """Current user (#10). `has_library` is present for owners only."""

    domain = DomainSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "phone", "role", "domain", "created_at"]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.role == User.Role.OWNER:
            data["has_library"] = getattr(instance, "library", None) is not None
        return data


class AccessTokenOutput(serializers.Serializer):
    access = serializers.CharField()


class AuthOutput(serializers.Serializer):
    access = serializers.CharField()
    user = UserSerializer()

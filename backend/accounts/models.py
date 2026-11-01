from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models


class Administrator(AbstractUser):
    """Report Figure 4.16, using Django's password and permissions system."""
    admin_id = models.AutoField(primary_key=True)
    username = models.CharField(
        max_length=100, unique=True, validators=[UnicodeUsernameValidator()],
    )
    email = models.EmailField(max_length=150)
    password = models.CharField(max_length=255, db_column="password_hash")

    class Meta:
        db_table = "administrator"
        verbose_name = "administrator"
        verbose_name_plural = "administrators"


from collections import OrderedDict
from datetime import date, timedelta
from logging import getLogger
from typing import Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser, UserManager as AbstractUserManager, Group
from django.core.cache import cache
from django.db import models
from django.db.models import Avg, Count, ExpressionWrapper, F, Sum
from django.db.models.functions import (
    Ceil,
    ExtractDay,
    ExtractMonth,
    ExtractWeek,
    ExtractYear,
    Greatest,
    TruncDay,
    TruncHour,
    TruncMonth,
    TruncMonth,
    TruncWeek,
)
from django.utils import timezone
from django.utils.functional import cached_property

logger = getLogger()


class Profile(models.Model):
    """These are accounts on the helpdesk system — people that can log in"""
    email_address = models.EmailField(unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=128, blank=True, null=True)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, blank=True, null=True)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username



class Company(models.Model):
    """Companies that have accounts on the reporting system"""
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=128, blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Companies'

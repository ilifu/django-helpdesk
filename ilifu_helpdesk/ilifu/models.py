from logging import getLogger

from django.contrib.auth import get_user_model
from django.db import models

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

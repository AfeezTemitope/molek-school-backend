from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile
from django import forms
import re


class UserProfileAdminForm(forms.ModelForm):
    """Form for UserProfile in Django admin"""

    class Meta:
        model = UserProfile
        fields = '__all__'

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and not re.match(r'^\+?1?\d{9,15}$', phone_number):
            raise forms.ValidationError('Invalid phone number format')
        return phone_number

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role not in ['admin', 'superadmin']:
            raise forms.ValidationError('Role must be admin or superadmin')
        return role

@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    """Admin interface for UserProfile"""
    form = UserProfileAdminForm
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'role',
        'is_active', 'is_staff', 'created_at'
    )
    list_filter = ('role', 'is_active', 'is_staff', 'sex')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': (
                'first_name', 'last_name', 'email', 'phone_number',
                'sex', 'age', 'address', 'state_of_origin', 'local_govt_area'
            )
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name', 'role',
                'phone_number', 'password1', 'password2'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        """Auto-set is_staff for admins/superadmins"""
        if obj.role in ['admin', 'superadmin']:
            obj.is_staff = True
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Only show admin/superadmin users"""
        qs = super().get_queryset(request)
        return qs.filter(role__in=['admin', 'superadmin'])
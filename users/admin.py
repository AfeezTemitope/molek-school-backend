from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile, Student
from django import forms
import re


class UserProfileAdminForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = '__all__'

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and not re.match(r'^\+?1?\d{9,15}$', phone_number):
            raise forms.ValidationError('Invalid phone number format')
        return phone_number


@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    form = UserProfileAdminForm
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'role',
        'sex', 'age', 'state_of_origin', 'local_govt_area',
        'is_active', 'created_at', 'updated_at'
    )
    list_filter = ('role', 'is_active', 'sex', 'state_of_origin')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'state_of_origin', 'local_govt_area')
    readonly_fields = ('created_at', 'updated_at', 'created_by')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': (
                'first_name', 'last_name', 'email', 'phone_number',
                'sex', 'age', 'address', 'state_of_origin', 'local_govt_area'
            )
        }),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name', 'role',
                'sex', 'age', 'address', 'state_of_origin', 'local_govt_area',
                'phone_number', 'password1', 'password2'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'admission_number', 'first_name', 'last_name', 'sex', 'age', 'state_of_origin',
        'local_govt_area', 'class_level', 'stream', 'section',
        'parent_email', 'parent_phone_number', 'is_active',
        'created_at', 'updated_at'
    )
    list_filter = ('class_level', 'stream', 'section', 'is_active', 'sex', 'state_of_origin')
    search_fields = ('admission_number', 'first_name', 'last_name', 'state_of_origin', 'local_govt_area')
    readonly_fields = ('admission_number', 'created_at', 'updated_at', 'created_by', 'full_name')

    fieldsets = (
        (None, {'fields': ('admission_number', 'first_name', 'last_name', 'full_name', 'age', 'sex')}),
        ('Personal Info', {'fields': ('address', 'state_of_origin', 'local_govt_area')}),
        ('Academic Info', {'fields': ('class_level', 'stream', 'section', 'passport')}),
        ('Parent Info', {'fields': ('parent_email', 'parent_phone_number')}),
        ('Status', {'fields': ('is_active',)}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

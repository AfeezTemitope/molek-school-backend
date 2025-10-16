import re

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile, Student
from django import forms

class UserProfileAdminForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = '__all__'

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and not re.match(r'^\+?1?\d{9,15}$', phone_number):
            raise forms.ValidationError('Invalid phone number format')
        return phone_number

class StudentAdminForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = '__all__'

    def clean_parent_phone_number(self):
        phone_number = self.cleaned_data.get('parent_phone_number')
        if phone_number and not re.match(r'^\+?1?\d{9,15}$', phone_number):
            raise forms.ValidationError('Invalid phone number format')
        return phone_number

@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    form = UserProfileAdminForm
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'created_at', 'updated_at')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role != 'superadmin':
            return qs.filter(created_by=request.user)
        return qs

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    list_display = ('admission_number', 'user', 'class_level', 'stream', 'section', 'parent_email', 'parent_phone_number', 'is_active', 'created_at', 'updated_at')
    list_filter = ('class_level', 'stream', 'section', 'is_active')
    search_fields = ('admission_number', 'user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('admission_number', 'created_at', 'updated_at', 'created_by')
    fieldsets = (
        (None, {'fields': ('user', 'admission_number')}),
        ('Academic Info', {'fields': ('class_level', 'stream', 'section', 'passport')}),
        ('Parent Info', {'fields': ('parent_email', 'parent_phone_number')}),
        ('Status', {'fields': ('is_active',)}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role != 'superadmin':
            return qs.filter(created_by=request.user)
        return qs